"""
CLI helpers for managing GitHub notifications.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import click
from rich.table import Table

from fown.core.utils.file_io import console, make_github_api_request

PAGE_SIZE = 10
DISPLAY_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
KEY_TO_INDEX = {key: idx for idx, key in enumerate(DISPLAY_KEYS)}
SUBJECT_URL_PATTERN = re.compile(r"/repos/([^/]+)/([^/]+)(?:/|$)")


def _fetch_notifications(include_all: bool = True) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"per_page": 100}
    if include_all:
        params["all"] = "true"
    data = make_github_api_request("GET", "notifications", params=params)
    return data if isinstance(data, list) else []


def _extract_repo_slug(notification: Dict[str, Any]) -> Optional[str]:
    repo_data = notification.get("repository")
    if isinstance(repo_data, dict):
        full_name = repo_data.get("full_name")
        if full_name:
            return full_name

    subject_url = (notification.get("subject") or {}).get("url") or ""
    match = SUBJECT_URL_PATTERN.search(subject_url)
    if match:
        owner, repo_name = match.group(1), match.group(2)
        return f"{owner}/{repo_name}"

    return None


def _filter_notifications(
    notifications: List[Dict[str, Any]], owner: Optional[str], repo: Optional[str]
) -> List[Dict[str, Any]]:
    if not owner and not repo:
        return notifications

    owner_lower = owner.lower() if owner else None
    repo_lower = repo.lower() if repo else None

    filtered: List[Dict[str, Any]] = []
    for notification in notifications:
        slug = _extract_repo_slug(notification)
        if not slug:
            continue

        slug_owner, slug_repo = slug.split("/", 1)
        if owner_lower and slug_owner.lower() != owner_lower:
            continue

        if repo_lower:
            repo_name_lower = slug_repo.lower()
            if not (repo_name_lower == repo_lower or repo_name_lower.startswith(repo_lower)):
                continue

        filtered.append(notification)

    return filtered


def _render_page(notifications: List[Dict[str, Any]], page: int, total_pages: int) -> None:
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(notifications))

    table = Table(title=f"Notifications {page + 1}/{total_pages}")
    table.add_column("Key", justify="right", style="cyan", no_wrap=True)
    table.add_column("Repository", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Title", style="white")
    table.add_column("Unread", justify="center", style="yellow")

    for offset, notification in enumerate(notifications[start:end]):
        key = DISPLAY_KEYS[offset]
        repo = _extract_repo_slug(notification) or notification.get("repository", {}).get(
            "full_name", "-"
        )
        subject = notification.get("subject", {})
        title = subject.get("title", "(no title)")
        notif_type = subject.get("type", "-")
        unread = "yes" if notification.get("unread") else "no"

        table.add_row(key, repo, notif_type, title, unread)

    console.print(table)


def _handle_page_navigation(page: int, total_pages: int, choice: str) -> Optional[int]:
    """Handle page navigation logic."""
    if choice == "n":
        return page + 1 if page < total_pages - 1 else page
    if choice == "p":
        return page - 1 if page > 0 else page
    return None


def _process_notification_selection(
    notifications: List[Dict[str, Any]], page: int, choice: str
) -> Optional[Dict[str, Any]]:
    """Process notification selection and return the selected notification."""
    if choice not in KEY_TO_INDEX:
        console.print("[warning]Unknown command. Use 1-0, n, p, or q.")
        return None

    selected_index = page * PAGE_SIZE + KEY_TO_INDEX[choice]
    if selected_index >= len(notifications):
        console.print("[warning]No notification mapped to that key on this page.")
        return None

    return notifications[selected_index]


def _initialize_notifications(
    owner: Optional[str], repo: Optional[str], unread_only: bool
) -> tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    """Initialize and filter notifications based on parameters."""
    owner = owner or os.getenv("FOWN_NOTI_OWNER") or os.getenv("OWNER")
    repo = repo or os.getenv("FOWN_NOTI_REPO") or os.getenv("REPO")

    include_all = not unread_only
    raw_notifications = _fetch_notifications(include_all=include_all)
    notifications = _filter_notifications(raw_notifications, owner=owner, repo=repo)

    return notifications, owner, repo


def _handle_notification_deletion(
    selected: Dict[str, Any], notifications: List[Dict[str, Any]], page: int, choice: str
) -> bool:
    """Handle the deletion of a selected notification. Returns True if deleted."""
    subject = selected.get("subject", {})
    repo_full = _extract_repo_slug(selected) or "-"
    title = subject.get("title", "(no title)")

    if not click.confirm(f"Delete notification '{title}' from '{repo_full}'?", default=False):
        return False

    thread_id = selected.get("id")
    if not thread_id:
        console.print("[error]Missing thread id; cannot delete this notification.")
        return False

    make_github_api_request("DELETE", f"notifications/threads/{thread_id}")
    console.print(f"[success]Deleted notification: {title}")
    notifications.pop(page * PAGE_SIZE + KEY_TO_INDEX[choice])
    return True


def _run_interactive_loop(
    notifications: List[Dict[str, Any]], owner: Optional[str], repo: Optional[str]
) -> None:
    """Run the main interactive loop for notification management."""
    page = 0
    while notifications:
        total_pages = max(1, (len(notifications) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        console.print()
        _render_page(notifications, page, total_pages)
        console.print("[info]Commands: 1-0 delete, n next page, p previous page, q quit")

        try:
            choice = click.prompt("Select", default="", show_default=False)
        except (click.Abort, EOFError):
            console.print("[warning]Input aborted. Exiting.")
            return

        choice = choice.strip().lower()
        if not choice:
            continue

        if choice == "q":
            console.print("[info]Exit requested. No further changes made.")
            return

        # Handle page navigation
        nav_result = _handle_page_navigation(page, total_pages, choice)
        if nav_result is not None:
            if nav_result == page:
                console.print(
                    f"[warning]Already at the {'last' if choice == 'n' else 'first'} page."
                )
            else:
                page = nav_result
            continue

        # Process notification selection and deletion
        selected = _process_notification_selection(notifications, page, choice)
        if not selected:
            continue

        if _handle_notification_deletion(selected, notifications, page, choice):
            # Adjust page if needed
            if page >= max(1, (len(notifications) + PAGE_SIZE - 1) // PAGE_SIZE):
                page = max(0, page - 1)


@click.group(name="noti")
def notifications_group() -> None:
    """Manage GitHub notifications."""


@notifications_group.command(name="delete")
@click.option(
    "--owner",
    "-o",
    help="Filter notifications to a specific repository owner (case-insensitive).",
)
@click.option(
    "--repo",
    "-r",
    help="Filter notifications by repository name or prefix (case-insensitive).",
)
@click.option(
    "--unread-only/--all",
    default=False,
    show_default=True,
    help="Show only unread notifications (default fetches all).",
)
def delete_notifications(owner: Optional[str], repo: Optional[str], unread_only: bool) -> None:
    """Delete notifications with an interactive pager."""
    # Initialize notifications and parameters
    notifications, owner, repo = _initialize_notifications(owner, repo, unread_only)
    raw_notifications = _fetch_notifications(include_all=not unread_only)

    # Check if any notifications were found
    if not notifications:
        if owner or repo:
            console.print(
                "[warning]No notifications found for the given filters "
                f"(owner={owner or '*'}, repo={repo or '*'})."
            )
        else:
            console.print("[warning]No notifications found.")
        return

    # Display filter information if applied
    if owner or repo:
        console.print(
            "[info]Filter applied: "
            f"owner={owner or '*'}, repo={repo or '*'} | "
            f"matched {len(notifications)}/{len(raw_notifications)} notifications."
        )

    # Run the interactive loop
    _run_interactive_loop(notifications, owner, repo)

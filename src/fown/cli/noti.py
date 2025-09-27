"""
CLI helpers for managing GitHub notifications.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import click
from rich.table import Table

from fown.core.utils.file_io import console, make_github_api_request

PAGE_SIZE = 10
DISPLAY_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
KEY_TO_INDEX = {key: idx for idx, key in enumerate(DISPLAY_KEYS)}
SUBJECT_URL_PATTERN = re.compile(r"/repos/([^/]+)/([^/]+)(?:/|$)")
UNKNOWN_REPO_SLUG = "<unknown>"


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
    notifications: List[Dict[str, Any]], owner: Optional[str], repo_filter: Optional[str]
) -> List[Dict[str, Any]]:
    if not owner and not repo_filter:
        return notifications

    owner_lower = owner.lower() if owner else None
    repo_lower = repo_filter.lower() if repo_filter else None

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


def _group_notifications_by_repo(
    notifications: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for notification in notifications:
        slug = _extract_repo_slug(notification) or UNKNOWN_REPO_SLUG
        grouped.setdefault(slug, []).append(notification)
    return grouped


def _remove_notifications_by_ids(
    notifications: List[Dict[str, Any]], ids_to_remove: set[str]
) -> None:
    if not ids_to_remove:
        return
    notifications[:] = [n for n in notifications if n.get("id") not in ids_to_remove]


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


def _handle_bulk_delete_confirmation(
    repo_slug: str, working: List[Dict[str, Any]], all_notifications: List[Dict[str, Any]]
) -> tuple[str, List[Dict[str, Any]]]:
    """Handle the bulk delete confirmation and execution."""
    thread_ids = [n.get("id") for n in working if n.get("id")]
    if not thread_ids:
        console.print("[warning]No thread IDs found; nothing to delete.")
        return "back", working

    confirm = click.confirm(
        f"Delete all {len(thread_ids)} notifications for '{repo_slug}'?",
        default=False,
    )
    if not confirm:
        return "continue", working

    errors = 0
    for thread_id in thread_ids:
        try:
            make_github_api_request("DELETE", f"notifications/threads/{thread_id}")
        except SystemExit:
            errors += 1

    if errors:
        console.print(f"[error]Failed to delete {errors} notification(s) for '{repo_slug}'.")
    else:
        console.print(f"[success]Deleted {len(thread_ids)} notification(s) for '{repo_slug}'.")

    valid_thread_ids = [tid for tid in thread_ids if tid is not None]
    _remove_notifications_by_ids(all_notifications, set(valid_thread_ids))
    updated_working = [n for n in working if n.get("id") not in set(valid_thread_ids)]
    return "deleted", updated_working


def _handle_repo_navigation(choice: str, page: int, total_pages: int) -> tuple[str, int]:
    """Handle navigation commands for repo bulk delete."""
    if choice == "q":
        console.print("[info]Exit requested. No further changes made.")
        return "quit", page
    if choice == "b":
        return "back", page
    if choice == "n":
        if page < total_pages - 1:
            return "continue", page + 1
        else:
            console.print("[warning]Already at the last page.")
            return "continue", page
    if choice == "p":
        if page > 0:
            return "continue", page - 1
        else:
            console.print("[warning]Already at the first page.")
            return "continue", page
    if choice == "y":
        return "delete", page

    console.print("[warning]Unknown command. Use y, n, p, b, or q.")
    return "continue", page


def _handle_repo_bulk_delete(
    repo_slug: str,
    repo_notifications: List[Dict[str, Any]],
    all_notifications: List[Dict[str, Any]],
) -> str:
    """Interactive bulk deletion flow for a single repository."""
    working = list(repo_notifications)
    page = 0

    while True:
        if not working:
            console.print(f"[success]No notifications remaining for {repo_slug}.")
            return "back"

        total_pages = max(1, (len(working) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        console.print()
        _render_page(working, page, total_pages)
        console.print("[info]Commands: y delete all, n next page, p previous page, b back, q quit")

        try:
            choice = click.prompt("Select", default="", show_default=False)
        except (click.Abort, EOFError):
            console.print("[warning]Input aborted. Exiting.")
            return "quit"

        choice = choice.strip().lower()
        if not choice:
            continue

        action, page = _handle_repo_navigation(choice, page, total_pages)
        if action in ("quit", "back"):
            return action
        elif action == "continue":
            continue
        elif action == "delete":
            result, working = _handle_bulk_delete_confirmation(
                repo_slug, working, all_notifications
            )
            if result in ("back", "deleted"):
                return result


def _render_repo_table(
    repo_entries: List[Tuple[str, List[Dict[str, Any]]]], page: int, total_pages: int
) -> None:
    """Render the repository selection table."""
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(repo_entries))

    table = Table(title=f"Repositories {page + 1}/{total_pages}")
    table.add_column("Key", justify="right", style="cyan", no_wrap=True)
    table.add_column("Repository", style="magenta")
    table.add_column("Total", justify="right", style="green")
    table.add_column("Unread", justify="right", style="yellow")

    for offset, (slug, items) in enumerate(repo_entries[start:end]):
        key = DISPLAY_KEYS[offset]
        unread_count = sum(1 for n in items if n.get("unread"))
        table.add_row(key, slug, str(len(items)), str(unread_count))

    console.print()
    console.print(table)
    console.print("[info]Commands: 1-0 select repo, n next page, p previous page, q quit")


def _handle_repo_selection_choice(
    choice: str,
    page: int,
    total_pages: int,
    repo_entries: List[Tuple[str, List[Dict[str, Any]]]],
    notifications: List[Dict[str, Any]],
) -> tuple[str, int]:
    """Handle user choice in repo selection loop."""
    if choice == "q":
        console.print("[info]Exit requested. No further changes made.")
        return "quit", page
    if choice == "n":
        if page < total_pages - 1:
            return "continue", page + 1
        else:
            console.print("[warning]Already at the last page.")
            return "continue", page
    if choice == "p":
        if page > 0:
            return "continue", page - 1
        else:
            console.print("[warning]Already at the first page.")
            return "continue", page

    if choice not in KEY_TO_INDEX:
        console.print("[warning]Unknown command. Use 1-0, n, p, or q.")
        return "continue", page

    start = page * PAGE_SIZE
    selected_index = start + KEY_TO_INDEX[choice]
    if selected_index >= len(repo_entries):
        console.print("[warning]No repository mapped to that key on this page.")
        return "continue", page

    repo_slug, repo_notifications = repo_entries[selected_index]
    result = _handle_repo_bulk_delete(repo_slug, repo_notifications, notifications)
    if result == "quit":
        return "quit", page
    if result == "deleted":
        return "continue", 0

    return "continue", page


def _repo_selection_loop(notifications: List[Dict[str, Any]]) -> None:
    """Interactive loop for selecting repositories to bulk delete."""
    page = 0
    while True:
        grouped = _group_notifications_by_repo(notifications)
        if not grouped:
            console.print("[success]No notifications remaining.")
            return

        repo_entries: List[Tuple[str, List[Dict[str, Any]]]] = sorted(
            grouped.items(), key=lambda item: item[0].lower()
        )
        total_pages = max(1, (len(repo_entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        _render_repo_table(repo_entries, page, total_pages)

        try:
            choice = click.prompt("Select", default="", show_default=False)
        except (click.Abort, EOFError):
            console.print("[warning]Input aborted. Exiting.")
            return

        choice = choice.strip().lower()
        if not choice:
            continue

        action, page = _handle_repo_selection_choice(
            choice, page, total_pages, repo_entries, notifications
        )
        if action == "quit":
            return


def _handle_notification_navigation(choice: str, page: int, total_pages: int) -> tuple[str, int]:
    """Handle navigation commands for notification loop."""
    if choice == "q":
        console.print("[info]Exit requested. No further changes made.")
        return "quit", page
    if choice == "n":
        if page < total_pages - 1:
            return "continue", page + 1
        else:
            console.print("[warning]Already at the last page.")
            return "continue", page
    if choice == "p":
        if page > 0:
            return "continue", page - 1
        else:
            console.print("[warning]Already at the first page.")
            return "continue", page

    return "select", page


def _process_single_notification_deletion(
    choice: str, page: int, notifications: List[Dict[str, Any]]
) -> tuple[str, int]:
    """Process deletion of a single notification."""
    if choice not in KEY_TO_INDEX:
        console.print("[warning]Unknown command. Use 1-0, n, p, or q.")
        return "continue", page

    selected_index = page * PAGE_SIZE + KEY_TO_INDEX[choice]
    if selected_index >= len(notifications):
        console.print("[warning]No notification mapped to that key on this page.")
        return "continue", page

    selected = notifications[selected_index]
    subject = selected.get("subject", {})
    repo_full = _extract_repo_slug(selected) or "-"
    title = subject.get("title", "(no title)")

    if not click.confirm(f"Delete notification '{title}' from '{repo_full}'?", default=False):
        return "continue", page

    thread_id = selected.get("id")
    if not thread_id:
        console.print("[error]Missing thread id; cannot delete this notification.")
        return "continue", page

    make_github_api_request("DELETE", f"notifications/threads/{thread_id}")
    console.print(f"[success]Deleted notification: {title}")
    notifications.pop(selected_index)

    # Adjust page if needed
    if page >= max(1, (len(notifications) + PAGE_SIZE - 1) // PAGE_SIZE):
        page = max(0, page - 1)

    return "continue", page


def _handle_notification_choice(
    choice: str, page: int, total_pages: int, notifications: List[Dict[str, Any]]
) -> tuple[str, int]:
    """Handle user choice in notification loop."""
    action, page = _handle_notification_navigation(choice, page, total_pages)
    if action in ("quit", "continue"):
        return action, page
    elif action == "select":
        return _process_single_notification_deletion(choice, page, notifications)
    else:
        # This should not happen, but ensure we always return something
        return "continue", page


def _run_notification_loop(notifications: List[Dict[str, Any]]) -> None:
    """Interactive loop for per-notification deletion."""
    page = 0
    while True:
        if not notifications:
            console.print("[success]No notifications remaining.")
            return

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

        action, page = _handle_notification_choice(choice, page, total_pages, notifications)
        if action == "quit":
            return


@click.group(name="noti")
def notifications_group() -> None:
    """Manage GitHub notifications."""


@notifications_group.command(name="delete")
@click.argument("target", required=False)
@click.option(
    "--owner",
    "-o",
    help="Filter notifications to a specific repository owner (case-insensitive).",
)
@click.option(
    "--repo-filter",
    "--filter",
    "-f",
    help="Filter notifications by repository name or prefix (case-insensitive).",
)
@click.option(
    "--unread-only/--all",
    default=False,
    show_default=True,
    help="Show only unread notifications (default fetches all).",
)
@click.option(
    "--repo",
    "-r",
    "repo_mode",
    is_flag=True,
    help="Group notifications by repository for bulk deletion.",
)
def delete_notifications(
    target: Optional[str],
    owner: Optional[str],
    repo_filter: Optional[str],
    unread_only: bool,
    repo_mode: bool,
) -> None:
    """Delete notifications interactively.

    Optionally provide TARGET as ``owner/repo`` (or just repo name) to apply filtering.
    Use ``--repo`` to bulk delete per repository.
    """

    target = target.strip() if target else None
    owner = owner.strip() if owner else None
    repo_filter = repo_filter.strip() if repo_filter else None

    if target:
        if "/" in target:
            target_owner, target_repo = target.split("/", 1)
            owner = target_owner.strip() or owner
            repo_filter = target_repo.strip() or repo_filter
        else:
            repo_filter = target

    env_owner = os.getenv("FOWN_NOTI_OWNER") or os.getenv("OWNER")
    env_repo = (
        os.getenv("FOWN_NOTI_REPO_FILTER") or os.getenv("FOWN_NOTI_REPO") or os.getenv("REPO")
    )

    owner = owner or (env_owner.strip() if env_owner else None)
    repo_filter = repo_filter or (env_repo.strip() if env_repo else None)

    include_all = not unread_only
    raw_notifications = _fetch_notifications(include_all=include_all)
    notifications = _filter_notifications(raw_notifications, owner=owner, repo_filter=repo_filter)

    if not notifications:
        if owner or repo_filter:
            console.print(
                "[warning]No notifications found for the given filters "
                f"(owner={owner or '*'}, repo={repo_filter or '*'})."
            )
        else:
            console.print("[warning]No notifications found.")
        return

    if owner or repo_filter:
        console.print(
            "[info]Filter applied: "
            f"owner={owner or '*'}, repo={repo_filter or '*'} | "
            f"matched {len(notifications)}/{len(raw_notifications)} notifications."
        )

    if repo_mode:
        grouped = _group_notifications_by_repo(notifications)
        if not grouped:
            console.print("[warning]No repositories found for bulk deletion.")
            return

        if target and len(grouped) == 1:
            repo_slug, repo_notifications = next(iter(grouped.items()))
            _handle_repo_bulk_delete(repo_slug, repo_notifications, notifications)
            return

        if target and len(grouped) > 1:
            console.print(
                "[info]Multiple repositories matched the provided target. "
                "Please choose from the list."
            )

        _repo_selection_loop(notifications)
        return

    _run_notification_loop(notifications)

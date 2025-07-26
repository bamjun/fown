"""
레이블 관련 명령어 모듈
"""

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import rich_click as click
import yaml
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Prompt
from rich.table import Table

from fown.core.models.config import Config, Label, Repository
from fown.core.services.github import LabelService
from fown.core.utils.file_io import console, get_git_repo_url, make_github_api_request


@click.group(name="labels")
def labels_group():
    """[bold yellow]레이블[/] 관련 명령어"""
    pass


def get_github_username() -> Optional[str]:
    """Get GitHub username via API."""
    try:
        user_data = make_github_api_request("GET", "user")
        # 명시적 타입 체크 추가
        if isinstance(user_data, dict):
            return user_data.get("login")
        return None
    except SystemExit:
        return None


def find_default_archive_repo() -> Tuple[bool, Optional[str], Optional[str]]:
    """Find the default fown-archive repository."""
    username = get_github_username()
    if not username:
        return False, None, None

    try:
        repos = make_github_api_request("GET", "user/repos", params={"per_page": 100})
        # 명시적 타입 체크 추가
        if not isinstance(repos, list):
            return False, None, None

        for repo in repos:
            if "fown-archive" in repo["name"]:
                try:
                    endpoint = f"repos/{username}/{repo['name']}/contents/.fown/config.yml"
                    config_data = make_github_api_request("GET", endpoint)
                    # 명시적 타입 체크 추가
                    if isinstance(config_data, dict) and "content" in config_data:
                        content = base64.b64decode(config_data["content"]).decode("utf-8")
                        config = yaml.safe_load(content)
                        if config and config.get("default_repository") is True:
                            return True, repo["name"], username
                except SystemExit:
                    continue
    except SystemExit:
        return False, None, None
    return False, None, None


def list_archive_label_files(repo_name: str, owner: str) -> List[Dict]:
    """List label files in the archive repository."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/labels"
        files_data = make_github_api_request("GET", endpoint)
        if isinstance(files_data, list):
            return [
                {"name": item["name"], "path": item["path"], "type": item["type"]}
                for item in files_data
                if item["type"] == "file" and item["name"].endswith(".json")
            ]
        return []
    except SystemExit:
        return []


def get_label_file_content(repo_name: str, owner: str, file_path: str) -> Optional[str]:
    """Get content of a specific label file."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/{file_path}"
        content_data = make_github_api_request("GET", endpoint)
        # 명시적 타입 체크 추가
        if isinstance(content_data, dict) and "content" in content_data:
            content = base64.b64decode(content_data["content"]).decode("utf-8")
            labels_data = json.loads(content)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".json", mode="w", encoding="utf-8"
            ) as tf:
                json.dump(labels_data, tf, ensure_ascii=False, indent=2)
                return tf.name
        return None
    except SystemExit:
        return None


def load_labels_from_json(file_path: str) -> List[Label]:
    """Load labels from a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Label.from_dict(item) for item in data]
    except (IOError, json.JSONDecodeError) as e:
        console.print(f"[error]레이블 파일 로드 실패:[/] {str(e)}")
        return []


def _display_paginated_menu(
    items: List[Dict],
    current_page: int,
    total_pages: int,
    border_style: str = "cyan",
    title_prefix: str = "",
    columns: Optional[List[Dict[str, str]]] = None,
) -> Table:
    """공통 페이지네이션 메뉴 표시 함수"""
    console.clear()
    console.print(
        Panel(
            f"{title_prefix}레이블 파일 목록 (페이지 {current_page}/{total_pages})",
            border_style=border_style,
        )
    )

    # 기본 컬럼 설정
    if columns is None:
        columns = [
            {"name": "#", "style": "cyan"},
            {"name": "파일명", "style": "green"},
            {"name": "타입", "style": "yellow"},
        ]

    # 테이블 생성
    table = Table(show_header=True)
    for col in columns:
        table.add_column(col["name"], style=col.get("style", ""))

    for i, item in enumerate(items, 1):
        row = [str(i)]
        row.extend(
            [
                item.get("name", "")
                if col["name"].lower() == "파일명"
                else os.path.splitext(item.get("name", ""))[1]
                if col["name"].lower() == "타입"
                else item.get(col["name"].lower(), "")
                for col in columns[1:]
            ]
        )
        table.add_row(*row)

    console.print(table)
    return table


def _handle_pagination_menu(
    files: List[Dict],
    repo_name: str,
    owner: str,
    page_size: int = 5,
    columns: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    """공통 페이지네이션 처리 함수"""
    current_page = 1

    while True:
        # 페이지네이션 계산
        total_pages = (len(files) + page_size - 1) // page_size
        start_index = (current_page - 1) * page_size
        end_index = start_index + page_size
        page_files = files[start_index:end_index]

        # 메뉴 표시
        _display_paginated_menu(
            page_files,
            current_page,
            total_pages,
            border_style="cyan",
            title_prefix="",
            columns=columns,
        )

        # 명령어 안내
        console.print("\n[bold]명령어:[/]")
        if total_pages > 1:
            console.print(f" 1-{len(page_files)}: 레이블 파일 선택")
            console.print(" n: 다음 페이지")
            console.print(" p: 이전 페이지")
        else:
            console.print(f" 1-{len(page_files)}: 레이블 파일 선택")
        console.print(" q: 종료")

        # 사용자 선택 처리
        choice = Prompt.ask("선택").strip().lower()

        # 종료 처리
        if choice == "q":
            return None

        # 페이지 이동 처리
        if choice == "n" and current_page < total_pages:
            current_page += 1
            continue
        elif choice == "p" and current_page > 1:
            current_page -= 1
            continue

        # 선택 검증
        try:
            index = int(choice)
            if 1 <= index <= len(page_files):
                selected_file = page_files[index - 1]
                return get_label_file_content(repo_name, owner, selected_file["path"])
            else:
                console.print("[warning]잘못된 선택입니다.[/warning]")
        except ValueError:
            console.print("[warning]숫자를 입력해주세요.[/warning]")


def load_labels_from_archive(
    repo_name: str, owner: str, show_menu: bool = False
) -> Tuple[List[Label], Optional[str]]:
    """Load labels from an archive repository."""
    labels: List[Label] = []
    temp_file_path: Optional[str] = None

    files = list_archive_label_files(repo_name, owner)
    if not files:
        console.print("[warning]No label files found in the archive.[/warning]")
        return labels, temp_file_path

    if show_menu:
        temp_file_path = _handle_pagination_menu(
            files,
            repo_name,
            owner,
            columns=[
                {"name": "#", "style": "cyan"},
                {"name": "파일명", "style": "green"},
                {"name": "타입", "style": "yellow"},
            ],
        )
    else:
        # 첫 번째 파일 사용
        temp_file_path = get_label_file_content(repo_name, owner, files[0]["path"])

    if temp_file_path:
        labels = load_labels_from_json(temp_file_path)

    return labels, temp_file_path


def apply_labels_to_repo(labels: List[Label], repo_full_name: str) -> int:
    """Apply labels to a repository."""
    success_count = 0
    with Progress() as progress:
        task = progress.add_task("[cyan]레이블 생성 중...[/]", total=len(labels))
        for label in labels:
            if label.name and label.color:
                if LabelService.create_label(label, repo_full_name):
                    success_count += 1
            progress.update(task, advance=1)
    return success_count


@labels_group.command(name="sync")
@click.option("--repo-url", default=None, help="Target GitHub Repository URL.")
@click.option("--labels-file", "-f", default=None, help="Path to labels YAML/JSON file.")
@click.option("--archive", is_flag=True, help="Use labels from an archive repository.")
@click.confirmation_option(prompt="Delete all existing labels and apply new ones?")
def sync_labels(repo_url: Optional[str], labels_file: Optional[str], archive: bool):
    """Synchronize labels by deleting all old ones and applying new ones."""
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)
    console.print(f"[info]Syncing labels for [bold]{repo.full_name}[/]...[/]")

    labels: List[Label] = []
    temp_file_path: Optional[str] = None

    if labels_file:
        labels = Config.load_labels(labels_file)
    else:
        found, repo_name, owner = find_default_archive_repo()
        if found and repo_name and owner:
            # show_menu 파라미터를 archive 옵션과 연결
            labels, temp_file_path = load_labels_from_archive(repo_name, owner, show_menu=archive)

        # 아카이브에서 레이블을 찾지 못했거나 아카이브 옵션이 없는 경우 기본 레이블 사용
        if not labels:
            console.print("[warning]No labels found in archive, using default.[/warning]")
            default_path = Path(__file__).parent.parent / "data/default_config.yml"
            labels = Config.load_labels(str(default_path))

    if not labels:
        console.print("[error]No labels to apply.[/error]")
        return

    console.print(f"[info]Deleting all existing labels from {repo.full_name}...[/]")
    LabelService.delete_all_labels(repo.full_name)

    console.print(f"[info]Applying {len(labels)} new labels...[/]")
    success_count = apply_labels_to_repo(labels, repo.full_name)

    console.print(
        Panel(f"[success]{success_count}/{len(labels)} labels synced.[/]", title="Complete")
    )

    # 임시 파일 정리
    if temp_file_path:
        os.unlink(temp_file_path)


@labels_group.command(name="clear-all")
@click.option("--repo-url", default=None, help="Target GitHub Repository URL.")
@click.confirmation_option(
    prompt="Are you sure you want to delete all labels? This cannot be undone."
)
def clear_all_labels(repo_url: Optional[str]):
    """Delete all labels from a repository."""
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)
    console.print(f"[info]Deleting all labels from [bold]{repo.full_name}[/]...[/]")
    LabelService.delete_all_labels(repo.full_name)


@labels_group.command(name="apply")
@click.option("--repo-url", default=None, help="Target GitHub Repository URL.")
@click.option("--labels-file", "-f", required=True, help="Path to labels YAML/JSON file.")
def apply_labels(repo_url: Optional[str], labels_file: str):
    """Create or update labels from a file."""
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)
    console.print(f"[info]Applying labels to [bold]{repo.full_name}[/]...[/]")

    labels = Config.load_labels(labels_file)
    console.print(f"[info]Loaded {len(labels)} labels.[/]")

    success_count = apply_labels_to_repo(labels, repo.full_name)
    console.print(
        Panel(f"[success]{success_count}/{len(labels)} labels applied.[/]", title="Complete")
    )

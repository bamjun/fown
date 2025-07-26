"""
스크립트 실행 관련 명령어 모듈
"""

import base64
import json
import os
import shutil  # shutil 모듈 추가
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import rich_click as click
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from fown.core.utils.file_io import console, make_github_api_request


@click.group(name="script")
def script_group():
    """[bold yellow]스크립트[/] 관련 명령어"""
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
        if not isinstance(repos, list):
            return False, None, None

        for repo in repos:
            if "fown-archive" in repo["name"]:
                try:
                    endpoint = f"repos/{username}/{repo['name']}/contents/.fown/config.yml"
                    config_data = make_github_api_request("GET", endpoint)
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


def list_archive_script_files(repo_name: str, owner: str) -> List[Dict]:
    """List script files in the archive repository."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/scripts"
        files_data = make_github_api_request("GET", endpoint)
        if isinstance(files_data, list):
            return [
                {
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],
                    "sha": item["sha"],
                }
                for item in files_data
                if item["type"] == "file"
                and (item["name"].endswith(".py") or item["name"].endswith(".sh"))
            ]
        return []
    except SystemExit:
        return []


def get_script_file_content(repo_name: str, owner: str, file_path: str) -> Optional[str]:
    """Get content of a specific script file."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/{file_path}"
        content_data = make_github_api_request("GET", endpoint)
        if isinstance(content_data, dict) and "content" in content_data:
            content = base64.b64decode(content_data["content"]).decode("utf-8")
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(file_path)[1], mode="w", encoding="utf-8"
            ) as tf:
                tf.write(content)
                return tf.name
        return None
    except SystemExit:
        return None


def run_script(script_path: str):
    """Executes a script file."""
    console.print(f"[info]Executing script: {script_path}[/]")
    try:
        if script_path.endswith(".py"):
            result = subprocess.run(
                [sys.executable, script_path], capture_output=True, text=True, check=False
            )
        elif script_path.endswith(".sh"):
            # Make script executable
            os.chmod(script_path, 0o755)
            result = subprocess.run(
                ["bash", script_path], capture_output=True, text=True, check=False
            )
        else:
            console.print(f"[error]Unsupported script type: {script_path}[/error]")
            return

        if result.stdout:
            console.print(Panel(result.stdout, title="Script Output", border_style="green"))
        if result.stderr:
            console.print(Panel(result.stderr, title="Script Error", border_style="red"))

    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)


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
            f"{title_prefix}스크립트 목록 (페이지 {current_page}/{total_pages})",
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
                else (
                    os.path.splitext(item.get("name", ""))[1]
                    if col["name"].lower() == "타입"
                    else item.get(col["name"].lower(), "")
                )
                for col in columns[1:]
            ]
        )
        table.add_row(*row)

    console.print(table)
    return table


def _handle_script_pagination_menu(
    files: List[Dict],
    repo_name: str,
    owner: str,
    action_func: Callable[[str], None],
    page_size: int = 5,
    columns: Optional[List[Dict[str, str]]] = None,
) -> None:
    """공통 스크립트 페이지네이션 처리 함수"""
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
            console.print(f" 1-{len(page_files)}: 스크립트 선택")
            console.print(" n: 다음 페이지")
            console.print(" p: 이전 페이지")
        else:
            console.print(f" 1-{len(page_files)}: 스크립트 선택")
        console.print(" q: 종료")

        # 사용자 선택 처리
        choice = Prompt.ask("선택").strip().lower()

        # 종료 처리
        if choice == "q":
            break

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
                script_path_temp = get_script_file_content(repo_name, owner, selected_file["path"])
                if script_path_temp:
                    action_func(script_path_temp)
                    break
            else:
                console.print("[warning]잘못된 선택입니다.[/warning]")
        except ValueError:
            console.print("[warning]숫자를 입력해주세요.[/warning]")


@script_group.command(name="use")
def use_script():
    """Execute a script from the archive repository."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]Default archive repository not found.[/error]")
        return

    files = list_archive_script_files(repo_name, owner)
    if not files:
        console.print("[warning]No scripts found in the archive.[/warning]")
        return

    _handle_script_pagination_menu(
        files=files, repo_name=repo_name, owner=owner, action_func=run_script
    )


@script_group.command(name="add")
@click.argument("script_path", type=click.Path(exists=True))
def add_script(script_path: str):
    """Add a script to the archive repository."""
    if not (script_path.endswith(".sh") or script_path.endswith(".py")):
        console.print("[error]Only .sh and .py scripts are supported.[/error]")
        return

    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]Default archive repository not found.[/error]")
        return

    with open(script_path, "rb") as f:
        content = f.read()

    file_name = os.path.basename(script_path)
    endpoint = f"repos/{owner}/{repo_name}/contents/scripts/{file_name}"
    data = {
        "message": f"Add script: {file_name}",
        "content": base64.b64encode(content).decode("utf-8"),
    }

    try:
        make_github_api_request("PUT", endpoint, data=data)
        console.print(f"[success]Script '{file_name}' added successfully.[/success]")
    except SystemExit:
        console.print(f"[error]Failed to add script '{file_name}'.[/error]")


@script_group.command(name="delete")
def delete_script():
    """Delete a script from the archive repository."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]Default archive repository not found.[/error]")
        return

    files = list_archive_script_files(repo_name, owner)
    if not files:
        console.print("[warning]No scripts found to delete.[/warning]")
        return

    for i, file in enumerate(files, 1):
        console.print(f"{i}. {file['name']}")
    choice_str = Prompt.ask(
        "Select a script to delete by number", choices=[str(i) for i in range(1, len(files) + 1)]
    )
    choice = int(choice_str) - 1

    selected_file = files[choice]

    if (
        not Prompt.ask(
            f"Are you sure you want to delete '{selected_file['name']}'?", choices=["y", "n"]
        )
        == "y"
    ):
        console.print("Deletion cancelled.")
        return

    endpoint = f"repos/{owner}/{repo_name}/contents/{selected_file['path']}"
    data = {
        "message": f"Delete script: {selected_file['name']}",
        "sha": selected_file["sha"],
    }

    try:
        make_github_api_request("DELETE", endpoint, data=data)
        console.print(f"[success]Script '{selected_file['name']}' deleted.[/success]")
    except SystemExit:
        console.print("[error]Failed to delete script.[/error]")


@script_group.command(name="load")
def load_script():
    """Download a script from the archive repository."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]Default archive repository not found.[/error]")
        return

    files = list_archive_script_files(repo_name, owner)
    if not files:
        console.print("[warning]No scripts found to load.[/warning]")
        return

    def download_action(script_path_temp: str):
        """다운로드 액션 함수"""
        dest_path = Path.cwd() / Path(script_path_temp).name
        # move the file
        shutil.move(script_path_temp, dest_path)
        console.print(f"[success]Script downloaded to {dest_path}[/success]")

    _handle_script_pagination_menu(
        files=files, repo_name=repo_name, owner=owner, action_func=download_action
    )

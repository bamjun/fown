"""
파일 관련 명령어 모듈
"""

import base64
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

import rich_click as click
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from fown.core.services.github import get_github_username, get_user_repositories
from fown.core.utils.file_io import console, make_github_api_request


@click.group(name="file")
def file_group():
    """[bold yellow]파일[/] 관련 명령어

    아카이브 레포지토리의 파일을 관리합니다.
    """
    pass


def find_default_archive_repo() -> Tuple[bool, Optional[str], Optional[str]]:
    """기본 아카이브 레포지토리 찾기"""
    username = get_github_username()
    if not username:
        console.print("[error]GitHub 사용자 정보를 가져올 수 없습니다.[/]")
        return False, None, None

    repos = get_user_repositories()
    repo_names = {repo["name"] for repo in repos}

    for i in range(10):
        suffix = "" if i == 0 else str(i)
        repo_name = f"fown-archive{suffix}"

        if repo_name in repo_names:
            try:
                endpoint = f"repos/{username}/{repo_name}/contents/.fown/config.yml"
                content_data = make_github_api_request("GET", endpoint)
                if isinstance(content_data, dict) and "content" in content_data:
                    content = base64.b64decode(content_data["content"]).decode("utf-8")
                    config = yaml.safe_load(content)
                    if config and config.get("default_repository") is True:
                        return True, repo_name, username
            except SystemExit:
                continue  # If repo exists but config is not found, continue

    return False, None, None


def list_archive_files(repo_name: str, owner: str, path: str = "files") -> List[Dict]:
    """아카이브 레포지토리의 특정 경로에 있는 파일/폴더 목록 가져오기"""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/{path}"
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
            ]
        return []
    except SystemExit:
        return []


@file_group.command(name="add")
@click.argument("path", type=click.Path(exists=True))
def add_file(path: str):
    """아카이브 레포지토리에 [bold green]파일 또는 폴더를 추가[/]합니다."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        return

    path_obj = Path(path)
    if path_obj.is_dir():
        upload_directory(path_obj, owner, repo_name)
    else:
        upload_file(path_obj, owner, repo_name)


def upload_file(file_path: Path, owner: str, repo_name: str, base_repo_path: str = "files"):
    """지정된 파일을 아카이브 레포지토리에 업로드합니다."""
    try:
        with open(file_path, "rb") as f:
            content_bytes = f.read()
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        repo_file_path = f"{base_repo_path}/{file_path.name}"
        endpoint = f"repos/{owner}/{repo_name}/contents/{repo_file_path}"

        # 기존 파일 존재 여부 확인
        try:
            existing_file = make_github_api_request("GET", endpoint)
        except SystemExit:
            existing_file = None

        # 파일 존재 시 처리
        if existing_file and isinstance(existing_file, dict):
            # 사용자에게 선택지 제공
            console.print(f"[yellow]파일 '{file_path.name}'이(가) 이미 존재합니다.[/]")
            console.print("[bold]작업을 선택하세요:[/]")
            console.print(" [bold green]o[/] 덮어쓰기")
            console.print(" [bold green]s[/] 새 이름으로 저장")
            console.print(" [bold green]n[/] 취소")

            action = Prompt.ask("선택", choices=["o", "s", "n"], default="n")

            if action == "n":
                console.print("[info]파일 업로드가 취소되었습니다.[/]")
                return

            if action == "s":
                # 새 이름 생성 (파일명_숫자.확장자)
                base_name = file_path.stem
                ext = file_path.suffix
                counter = 1
                while True:
                    new_filename = f"{base_name}_{counter}{ext}"
                    new_repo_path = f"{base_repo_path}/{new_filename}"
                    try:
                        make_github_api_request(
                            "GET", f"repos/{owner}/{repo_name}/contents/{new_repo_path}"
                        )
                        counter += 1
                    except SystemExit:
                        # 새 파일명으로 경로 업데이트
                        repo_file_path = new_repo_path
                        break

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            progress.add_task(
                description=f"[cyan]파일 업로드 중: {Path(repo_file_path).name}[/]", total=None
            )

            payload = {
                "message": f"Add file: {Path(repo_file_path).name}",
                "content": content_base64,
                "branch": "main",
            }

            # 기존 파일 덮어쓰기의 경우 SHA 추가
            if existing_file and isinstance(existing_file, dict) and "sha" in existing_file:
                payload["sha"] = existing_file["sha"]

            make_github_api_request(
                "PUT", f"repos/{owner}/{repo_name}/contents/{repo_file_path}", data=payload
            )
            console.print(
                f"[success]파일 [bold]{Path(repo_file_path).name}[/]이(가) 성공적으로 업로드되었습니다![/]"
            )

    except (SystemExit, Exception) as e:
        console.print(f"[error]파일 업로드 중 오류 발생:[/] {str(e)}")


def upload_directory(dir_path: Path, owner: str, repo_name: str) -> None:
    """지정된 디렉토리의 모든 파일을 아카이브 레포지토리에 업로드합니다."""
    console.print(f"[info]디렉토리 업로드 시작: [bold]{dir_path.name}[/][/]")
    for root, _, files in os.walk(dir_path):
        for file in files:
            local_path = Path(root) / file
            relative_path = local_path.relative_to(dir_path)
            repo_path = f"files/{dir_path.name}/{relative_path}"
            endpoint = f"repos/{owner}/{repo_name}/contents/{repo_path}"

            try:
                with open(local_path, "rb") as f:
                    content_bytes = f.read()
                content_base64 = base64.b64encode(content_bytes).decode("utf-8")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task(
                        description=f"[cyan]파일 업로드 중: {local_path.name}[/]", total=None
                    )
                    payload = {
                        "message": f"Add file: {local_path.name}",
                        "content": content_base64,
                        "branch": "main",
                    }
                    make_github_api_request("PUT", endpoint, data=payload)
                    console.print(
                        f"[success]파일 [bold]{local_path.name}[/]이(가) 성공적으로 업로드되었습니다![/]"
                    )

            except (SystemExit, Exception) as e:
                console.print(f"[error]파일 '{local_path.name}' 업로드 중 오류 발생:[/] {str(e)}")


@file_group.command(name="load")
def load_file():
    """아카이브 레포지토리의 [bold green]파일 또는 폴더를 다운로드[/]합니다."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        return

    navigate_and_download(owner, repo_name, "files")


def _handle_directory_download(owner: str, repo_name: str, selected_item: Dict) -> Optional[str]:
    """디렉토리 다운로드를 처리합니다."""
    action = Prompt.ask(
        f"'{selected_item['name']}'은(는) 디렉토리입니다. 전체 다운로드(y) 또는 폴더 진입(n) 중 선택하세요.",
        choices=["y", "n"],
        default="y",
    )
    if action == "y":
        download_directory(owner, repo_name, selected_item["path"])
        return None  # 다운로드 후 종료
    else:
        return selected_item["path"]  # 폴더 진입


def _validate_user_choice(choice: str, items_length: int) -> Optional[int]:
    """사용자 선택을 검증하고 유효한 인덱스를 반환합니다."""
    if not choice.isdigit():
        console.print("[warning]숫자를 입력해주세요.[/]")
        return None

    try:
        index = int(choice)
        if 1 <= index <= items_length:
            return index
        console.print("[warning]잘못된 선택입니다.[/]")
        return None
    except ValueError:
        console.print("[warning]유효한 숫자를 입력해주세요.[/]")
        return None


def _process_download_selection(
    owner: str, repo_name: str, current_path: str, selected_item: Dict
) -> Optional[str]:
    """선택된 항목에 대한 다운로드 처리를 수행합니다."""
    if selected_item["type"] == "dir":
        # 디렉토리 다운로드 처리
        action = Prompt.ask(
            f"'{selected_item['name']}'은(는) 디렉토리입니다. 전체 다운로드(y) 또는 폴더 진입(n) 중 선택하세요.",
            choices=["y", "n"],
            default="y",
        )
        if action == "y":
            download_directory(owner, repo_name, selected_item["path"])
            return None  # 다운로드 후 종료
        else:
            return selected_item["path"]  # 폴더 진입
    else:
        # 파일 다운로드
        download_item(owner, repo_name, selected_item)
        return None  # 다운로드 후 종료


def _display_paginated_menu(
    items: List[Dict],
    current_path: str,
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
            f"{title_prefix}[bold]{current_path}[/] 경로의 내용 (페이지 {current_page}/{total_pages})",
            border_style=border_style,
        )
    )

    # 기본 컬럼 설정
    if columns is None:
        columns = [
            {"name": "#", "style": "cyan"},
            {"name": "이름", "style": "green"},
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
                if col["name"].lower() == "이름"
                else item.get("type", "")
                if col["name"].lower() == "타입"
                else item.get(col["name"].lower(), "")
                for col in columns[1:]
            ]
        )
        table.add_row(*row)

    console.print(table)
    return table


def _validate_page_choice(
    choice: str, page_files: List[Dict], current_page: int, total_pages: int
) -> Optional[Union[Literal["back", "next", "prev", "retry"], int]]:
    """페이지 선택을 검증하고 처리합니다."""
    # 종료 처리
    if choice == "q":
        return None

    # 뒤로가기 처리
    if choice == "b":
        return "back"

    # 페이지 이동 처리
    if choice == "n" and current_page < total_pages:
        return "next"
    elif choice == "p" and current_page > 1:
        return "prev"

    # 항목 선택 처리
    try:
        index = int(choice)
        if 1 <= index <= len(page_files):
            return index
        console.print("[warning]잘못된 선택입니다.[/warning]")
    except ValueError:
        console.print("[warning]숫자를 입력해주세요.[/warning]")

    return "retry"


def _handle_pagination_menu(
    files: List[Dict],
    process_selection_func: Callable,
    repo_name: str,
    owner: str,
    current_path: str,
    page_size: int = 5,
    border_style: str = "cyan",
    title_prefix: str = "",
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
            page_files, current_path, current_page, total_pages, border_style, title_prefix, columns
        )

        # 명령어 안내
        console.print("\n[bold]명령어:[/]")
        if total_pages > 1:
            console.print(f" 1-{len(page_files)}: 항목 선택")
            console.print(" n: 다음 페이지")
            console.print(" p: 이전 페이지")
        else:
            console.print(f" 1-{len(page_files)}: 항목 선택")
        console.print(" b: 뒤로가기")
        console.print(" q: 종료")

        # 사용자 선택 처리
        choice = Prompt.ask("선택").strip().lower()

        # 선택 검증 및 처리
        validation_result = _validate_page_choice(choice, page_files, current_page, total_pages)

        # 결과에 따른 처리
        if validation_result is None:
            return None
        elif validation_result == "back":
            if current_path == "files":
                return None
            return str(Path(current_path).parent)
        elif validation_result == "next":
            current_page += 1
            continue
        elif validation_result == "prev":
            current_page -= 1
            continue
        elif validation_result == "retry":
            continue

        # 항목 선택 처리 (validation_result는 이제 확실히 int)
        selected_item = page_files[validation_result - 1]
        result = process_selection_func(owner, repo_name, current_path, selected_item)

        # 결과에 따른 처리
        if result is None:
            return None
        current_path = result
        current_page = 1


def navigate_and_download(owner: str, repo_name: str, current_path: str):
    """파일/폴더를 탐색하고 다운로드/뒤로가기 옵션을 제공합니다."""
    # 파일/폴더 목록 가져오기
    items = list_archive_files(repo_name, owner, current_path)
    if not items:
        console.print("[warning]파일이나 폴더가 없습니다.[/]")
        return

    # 페이지네이션 및 다운로드 처리
    _handle_pagination_menu(
        files=items,
        process_selection_func=_process_download_selection,
        repo_name=repo_name,
        owner=owner,
        current_path=current_path,
        border_style="cyan",
        title_prefix="레포지토리의 파일 목록 ",
    )


def download_item(owner: str, repo_name: str, item: Dict):
    """선택된 파일 또는 폴더를 다운로드합니다."""
    if item["type"] == "file":
        download_single_file(owner, repo_name, item)
    elif item["type"] == "dir":
        download_directory(owner, repo_name, item["path"])


def download_single_file(owner: str, repo_name: str, file_item: Dict, local_dir: Path = Path.cwd()):
    """단일 파일을 다운로드합니다."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/{file_item['path']}"
        content_data = make_github_api_request("GET", endpoint)
        # 명시적 타입 체크 추가
        if isinstance(content_data, dict) and "content" in content_data:
            content = base64.b64decode(content_data["content"])
            local_path = local_dir / file_item["name"]
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if local_path.exists():
                if (
                    not Prompt.ask(
                        f"[yellow]파일 '{local_path}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?[/]",
                        choices=["y", "n"],
                        default="n",
                    )
                    == "y"
                ):
                    console.print("[info]다운로드가 취소되었습니다.[/]")
                    return

            with open(local_path, "wb") as f:
                f.write(content)
            console.print(f"[success]파일 [bold]{file_item['name']}[/] 다운로드 완료![/]")
        else:
            console.print(
                f"[warning]파일 [bold]{file_item['name']}[/]의 내용을 가져올 수 없습니다.[/]"
            )

    except (SystemExit, Exception) as e:
        console.print(f"[error]파일 다운로드 실패:[/] {e}")


def download_directory(owner: str, repo_name: str, dir_path: str):
    """디렉토리 내용을 재귀적으로 다운로드합니다."""
    console.print(f"[info]디렉토리 다운로드 시작: [bold]{dir_path}[/][/]")
    items = list_archive_files(repo_name, owner, dir_path)

    # 명시적 타입 체크 추가
    if not isinstance(items, list):
        console.print(f"[warning]디렉토리 [bold]{dir_path}[/]의 내용을 가져올 수 없습니다.[/]")
        return

    local_dir_name = Path(dir_path).name
    local_base_dir = Path.cwd() / local_dir_name

    for item in items:
        if item["type"] == "file":
            download_single_file(owner, repo_name, item, local_base_dir)
        elif item["type"] == "dir":
            download_directory(owner, repo_name, item["path"])


@file_group.command(name="delete")
def delete_file():
    """아카이브 레포지토리의 [bold red]파일 또는 폴더를 삭제[/]합니다."""
    found, repo_name, owner = find_default_archive_repo()
    if not found or not repo_name or not owner:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        return

    navigate_and_delete(owner, repo_name, "files")


def _validate_delete_choice(choice: str, items_length: int) -> Optional[int]:
    """삭제 선택을 검증하고 유효한 인덱스를 반환합니다."""
    if not choice.isdigit():
        console.print("[warning]숫자를 입력해주세요.[/]")
        return None

    try:
        index = int(choice)
        if 1 <= index <= items_length:
            return index
        console.print("[warning]잘못된 선택입니다.[/]")
        return None
    except ValueError:
        console.print("[warning]유효한 숫자를 입력해주세요.[/]")
        return None


def _process_delete_selection(
    owner: str, repo_name: str, current_path: str, selected_item: Dict
) -> Optional[str]:
    """선택된 항목에 대한 삭제 처리를 수행합니다."""
    if selected_item["type"] == "dir":
        # 디렉토리 삭제 처리
        action = Prompt.ask(
            f"'{selected_item['name']}'은(는) 디렉토리입니다. 전체 삭제(y) 또는 폴더 진입(n) 중 선택하세요.",
            choices=["y", "n"],
            default="n",
        )
        if action == "y":
            # 디렉토리 삭제 확인
            confirm = Prompt.ask(
                f"[bold red]정말로 '{selected_item['name']}' 디렉토리와 모든 하위 파일을 삭제하시겠습니까?[/]",
                choices=["y", "n"],
                default="n",
            )
            if confirm == "y":
                delete_directory_recursive(owner, repo_name, selected_item["path"])
                return None  # 삭제 후 종료
            return current_path
        else:
            return selected_item["path"]  # 폴더 진입
    else:
        # 파일 삭제 처리
        confirm = Prompt.ask(
            f"[bold red]정말로 '{selected_item['name']}'을(를) 삭제하시겠습니까?[/]",
            choices=["y", "n"],
            default="n",
        )
        if confirm == "y":
            delete_single_file(owner, repo_name, selected_item)
        return current_path


def navigate_and_delete(owner: str, repo_name: str, current_path: str):
    """파일/폴더를 탐색하고 삭제/뒤로가기 옵션을 제공합니다."""
    # 파일/폴더 목록 가져오기
    items = list_archive_files(repo_name, owner, current_path)
    if not items:
        console.print("[warning]파일이나 폴더가 없습니다. 상위 폴더로 이동합니다.[/]")
        return

    # 페이지네이션 및 삭제 처리
    _handle_pagination_menu(
        files=items,
        process_selection_func=_process_delete_selection,
        repo_name=repo_name,
        owner=owner,
        current_path=current_path,
        border_style="red",
        title_prefix="경로의 내용 ",
    )


def delete_single_file(owner: str, repo_name: str, file_item: Dict):
    """단일 파일을 삭제합니다."""
    try:
        endpoint = f"repos/{owner}/{repo_name}/contents/{file_item['path']}"
        payload = {
            "message": f"Delete file: {file_item['name']}",
            "sha": file_item["sha"],
            "branch": "main",
        }
        make_github_api_request("DELETE", endpoint, data=payload)
        console.print(f"[success]파일 [bold]{file_item['name']}[/] 삭제 완료![/]")
    except (SystemExit, Exception) as e:
        console.print(f"[error]파일 삭제 중 오류 발생:[/] {e}")


def delete_directory_recursive(owner: str, repo_name: str, dir_path: str):
    """디렉토리와 그 내용을 재귀적으로 삭제합니다."""
    items = list_archive_files(repo_name, owner, dir_path)
    for item in items:
        if item["type"] == "dir":
            delete_directory_recursive(owner, repo_name, item["path"])
        else:
            delete_single_file(owner, repo_name, item)

    console.print(f"[success]디렉토리 [bold]{Path(dir_path).name}[/]의 내용이 삭제되었습니다.[/]")


if __name__ == "__main__":
    file_group()

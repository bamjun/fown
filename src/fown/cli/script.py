"""
스크립트 실행 관련 명령어 모듈
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url, run_gh_command


@click.group(name="script")
def script_group():
    """[bold yellow]스크립트[/] 관련 명령어

    아카이브 레포지토리의 스크립트를 실행합니다.
    """
    pass


def find_default_archive_repo() -> Tuple[bool, Optional[str], Optional[str]]:
    """기본 아카이브 레포지토리 찾기
    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            (찾았는지 여부, 레포지토리 이름, 레포지토리 소유자)
    """
    try:
        # 현재 인증된 사용자 정보 가져오기
        from fown.cli.archive import get_github_username, get_user_repositories

        username = get_github_username()
        if not username:
            console.print("[error]GitHub 사용자 정보를 가져올 수 없습니다.[/]")
            console.print("GitHub CLI에 로그인되어 있는지 확인하세요: gh auth login")
            return False, None, None

        # 사용자의 레포지토리 목록 가져오기
        repos = get_user_repositories()
        repo_names = {repo["name"] for repo in repos}

        # fown-archive부터 fown-archive9까지 확인
        for i in range(10):
            suffix = "" if i == 0 else str(i)
            repo_name = f"fown-archive{suffix}"

            if repo_name not in repo_names:
                continue

            console.print(f"[info]레포지토리 [bold]{repo_name}[/] 발견, 설정 확인 중...[/]")

            # 레포지토리가 존재하면 .fown/config.yml 파일 확인
            try:
                config_args = ["api", f"/repos/{username}/{repo_name}/contents/.fown/config.yml"]
                config_stdout, _ = run_gh_command(config_args)

                if config_stdout:
                    # base64로 인코딩된 내용을 디코딩
                    import base64

                    content_data = json.loads(config_stdout)
                    if "content" in content_data:
                        content = base64.b64decode(content_data["content"]).decode("utf-8")
                        import yaml

                        config = yaml.safe_load(content)

                        # default_repository 값 확인
                        if config and config.get("default_repository") is True:
                            console.print(f"[info]기본 레포지토리 [bold]{repo_name}[/] 발견![/]")
                            return True, repo_name, username
            except Exception:
                # config.yml 파일이 없거나 접근할 수 없는 경우 무시
                pass

        console.print("[info]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        return False, None, None
    except Exception as e:
        console.print(f"[error]레포지토리 확인 실패:[/] {str(e)}")
        return False, None, None


def list_archive_script_files(repo_name: str, owner: str) -> List[Dict]:
    """아카이브 레포지토리의 scripts 디렉토리에 있는 파일 목록 가져오기
    Args:
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
    Returns:
        List[Dict]: 파일 목록 (이름, 경로, 타입)
    """
    try:
        args = ["api", f"/repos/{owner}/{repo_name}/contents/scripts"]
        stdout, _ = run_gh_command(args)

        if stdout:
            files_data = json.loads(stdout)
            return [
                {"name": item["name"], "path": item["path"], "type": item["type"]}
                for item in files_data
                if item["type"] == "file"
                and (item["name"].endswith(".py") or item["name"].endswith(".sh"))
            ]
        return []
    except Exception as e:
        console.print(f"[warning]스크립트 파일 목록 가져오기 실패: {str(e)}[/]")
        return []


def get_script_file_content(repo_name: str, owner: str, file_path: str) -> Optional[str]:
    """아카이브 레포지토리에서 특정 스크립트 파일 내용 가져오기
    Args:
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
        file_path: 파일 경로
    Returns:
        Optional[str]: 임시 파일 경로 또는 None
    """
    try:
        args = ["api", f"/repos/{owner}/{repo_name}/contents/{file_path}"]
        stdout, _ = run_gh_command(args)

        if stdout:
            # base64로 인코딩된 내용을 디코딩
            import base64

            content_data = json.loads(stdout)
            if "content" in content_data:
                content = base64.b64decode(content_data["content"]).decode("utf-8")

                # 임시 파일에 저장
                file_name = os.path.basename(file_path)
                temp_dir = tempfile.gettempdir()
                temp_file_name = (
                    f"fown_script_{os.urandom(6).hex()}{os.path.splitext(file_name)[1]}"
                )
                temp_file_path = os.path.join(temp_dir, temp_file_name)

                with open(temp_file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                return temp_file_path
        return None
    except Exception as e:
        console.print(f"[error]스크립트 파일 내용 가져오기 실패:[/] {str(e)}")
        return None


def show_script_files_menu(files: List[Dict], repo_name: str, owner: str) -> Optional[str]:
    """스크립트 파일 선택 메뉴 표시
    Args:
        files: 파일 목록
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
    Returns:
        Optional[str]: 선택한 스크립트 파일 경로 또는 None
    """
    if not files:
        console.print("[warning]사용 가능한 스크립트 파일이 없습니다.[/]")
        return None

    page_size = 5
    current_page = 0
    total_pages = (len(files) + page_size - 1) // page_size

    while True:
        console.clear()
        console.print(
            Panel(
                f"[bold]{repo_name}[/] 레포지토리의 스크립트 파일 목록 (페이지 {current_page + 1}/{total_pages})",
                border_style="cyan",
            )
        )

        # 현재 페이지에 표시할 파일 목록
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(files))
        current_files = files[start_idx:end_idx]

        # 테이블 생성
        table = Table(show_header=True)
        table.add_column("#", style="cyan", justify="right")
        table.add_column("파일명", style="green")
        table.add_column("경로", style="dim")

        # 파일 목록 표시
        for i, file in enumerate(current_files, 1):
            table.add_row(str(i), file["name"], file["path"])

        console.print(table)

        # 안내 메시지
        console.print("\n[bold]명령어:[/]")
        console.print(" 1-5: 파일 선택")
        if total_pages > 1:
            console.print(" n: 다음 페이지")
            console.print(" p: 이전 페이지")
        console.print(" q: 종료")

        # 사용자 입력 받기
        choice = Prompt.ask("선택").strip().lower()

        if choice == "q":
            return None
        elif choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(current_files):
                file_idx = start_idx + idx - 1
                file_path = files[file_idx]["path"]
                console.print(f"[info]선택한 파일: [bold]{files[file_idx]['name']}[/][/]")
                return get_script_file_content(repo_name, owner, file_path)
            else:
                console.print("[error]잘못된 선택입니다. 다시 시도하세요.[/]")
                import time

                time.sleep(1)


def run_python_script(script_path: str) -> subprocess.CompletedProcess:
    """Python 스크립트를 실행합니다.

    Args:
        script_path: 스크립트 파일 경로

    Returns:
        subprocess.CompletedProcess: 실행 결과
    """
    return subprocess.run(
        [sys.executable, script_path], capture_output=True, text=True, encoding="utf-8"
    )


def find_bash_path() -> Optional[str]:
    """Windows 환경에서 bash 실행 파일 경로를 찾습니다.

    Returns:
        Optional[str]: bash 실행 파일 경로 또는 None
    """
    git_bash_paths = [
        "C:\\Program Files\\Git\\bin\\bash.exe",
        "C:\\Program Files (x86)\\Git\\bin\\bash.exe",
    ]
    for path in git_bash_paths:
        if os.path.exists(path):
            return path
    return None


def run_shell_script(script_path: str) -> Optional[subprocess.CompletedProcess]:
    """Shell 스크립트를 실행합니다.

    Args:
        script_path: 스크립트 파일 경로

    Returns:
        Optional[subprocess.CompletedProcess]: 실행 결과 또는 None
    """
    if os.name == "nt":
        # Windows 환경
        bash_path = find_bash_path()
        if bash_path:
            # Git Bash로 실행
            return subprocess.run(
                [bash_path, script_path], capture_output=True, text=True, encoding="utf-8"
            )
        else:
            # Git Bash가 없으면 WSL 시도
            try:
                return subprocess.run(
                    ["wsl", "bash", script_path], capture_output=True, text=True, encoding="utf-8"
                )
            except FileNotFoundError:
                console.print(
                    "[error]Windows에서 bash를 찾을 수 없습니다. Git Bash 또는 WSL을 설치하세요.[/]"
                )
                return None
    else:
        # Linux/Mac에서는 기본 bash 사용
        return subprocess.run(
            ["bash", script_path], capture_output=True, text=True, encoding="utf-8"
        )


def display_script_result(result: subprocess.CompletedProcess) -> None:
    """스크립트 실행 결과를 출력합니다.

    Args:
        result: 스크립트 실행 결과
    """
    if result.returncode == 0:
        if result.stdout:  # stdout이 None이 아닐 때만 출력
            console.print(Panel(result.stdout, title="스크립트 실행 성공", border_style="green"))
        else:
            console.print(
                Panel(
                    "스크립트가 성공적으로 실행되었습니다.",
                    title="스크립트 실행 성공",
                    border_style="green",
                )
            )
    else:
        error_message = result.stderr if result.stderr else "알 수 없는 오류"
        console.print(
            Panel(
                f"[error]에러 코드: {result.returncode}[/]\n\n{error_message}",
                title="스크립트 실행 실패",
                border_style="red",
            )
        )


def run_script(script_path: str) -> None:
    """스크립트 실행

    Args:
        script_path: 스크립트 파일 경로
    """
    try:
        file_ext = os.path.splitext(script_path)[1].lower()
        script_name = os.path.basename(script_path)

        console.print(f"[info]스크립트 파일 경로: [dim]{script_path}[/][/]")

        result = None
        if file_ext == ".py":
            # Python 스크립트 실행
            console.print(f"[info]Python 스크립트 실행 중: [bold]{script_name}[/][/]")
            result = run_python_script(script_path)
        elif file_ext == ".sh":
            # Shell 스크립트 실행
            console.print(f"[info]Shell 스크립트 실행 중: [bold]{script_name}[/][/]")
            result = run_shell_script(script_path)
        else:
            console.print(f"[error]지원하지 않는 스크립트 형식: {file_ext}[/]")
            return

        if result:
            display_script_result(result)

    except Exception as e:
        console.print(f"[error]스크립트 실행 실패:[/] {str(e)}")
    finally:
        # 임시 파일 삭제
        try:
            if os.path.exists(script_path):
                os.unlink(script_path)
        except Exception as e:
            console.print(f"[warning]임시 파일 삭제 실패: {str(e)}[/]")


@script_group.command(name="use")
def use_script():
    """아카이브 레포지토리의 [bold green]스크립트를 실행[/]합니다.

    기본 아카이브 레포지토리의 scripts/ 폴더에서 스크립트를 선택하여 실행합니다.
    """
    check_gh_installed()

    # 기본 아카이브 레포지토리 찾기
    found, repo_name, owner = find_default_archive_repo()
    if not found:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        console.print("먼저 make-fown-archive 명령어로 기본 아카이브 레포지토리를 생성하세요.")
        return

    # 스크립트 파일 목록 가져오기
    files = list_archive_script_files(repo_name, owner)
    if not files:
        console.print(
            f"[warning][bold]{repo_name}[/] 레포지토리의 scripts/ 폴더에 스크립트 파일이 없습니다.[/]"
        )
        console.print("scripts/ 폴더에 .py 또는 .sh 파일을 추가하세요.")
        return

    # 스크립트 파일 선택 메뉴 표시
    script_path = show_script_files_menu(files, repo_name, owner)
    if script_path:
        # 선택한 스크립트 실행
        run_script(script_path)


@script_group.command(name="add")
@click.argument("script_path", type=click.Path(exists=True))
def add_script(script_path: str):
    """아카이브 레포지토리에 [bold green]스크립트를 추가[/]합니다.

    스크립트 파일(.sh)을 기본 아카이브 레포지토리의 scripts/ 폴더에 업로드합니다.
    """
    check_gh_installed()

    # 파일 확장자 확인
    if not script_path.lower().endswith(".sh"):
        console.print("[error]'.sh' 확장자를 가진 스크립트 파일만 업로드할 수 있습니다.[/]")
        return

    # 기본 아카이브 레포지토리 찾기
    found, repo_name, owner = find_default_archive_repo()
    if not found:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        console.print("먼저 make-fown-archive 명령어로 기본 아카이브 레포지토리를 생성하세요.")
        return

    try:
        # 파일 내용 읽기
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()

        # base64로 인코딩
        import base64

        content_bytes = content.encode("utf-8")
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        # 파일 이름 추출
        file_name = os.path.basename(script_path)

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            # 진행 상태 표시
            progress.add_task(
                description=f"[cyan]스크립트 파일 업로드 중: {file_name}[/]", total=None
            )

            # GitHub API를 통해 파일 업로드
            args = [
                "api",
                f"/repos/{owner}/{repo_name}/contents/scripts/{file_name}",
                "--method",
                "PUT",
                "-f",
                f"message=Add script: {file_name}",
                "-f",
                f"content={content_base64}",
                "-f",
                "branch=main",
            ]
            stdout, stderr = run_gh_command(args)

            if stdout and not stderr:
                console.print(
                    f"[success]스크립트 파일 [bold]{file_name}[/]이(가) 성공적으로 업로드되었습니다![/]"
                )
            else:
                console.print(f"[error]스크립트 파일 업로드 실패:[/] {stderr or '알 수 없는 오류'}")

    except Exception as e:
        console.print(f"[error]스크립트 파일 업로드 중 오류 발생:[/] {str(e)}")


def delete_script_file(owner: str, repo_name: str, selected_file: Dict[str, str]) -> bool:
    """스크립트 파일을 삭제합니다.

    Args:
        owner: 레포지토리 소유자
        repo_name: 레포지토리 이름
        selected_file: 선택된 파일 정보

    Returns:
        bool: 삭제 성공 여부
    """
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            # 진행 상태 표시
            progress.add_task(
                description=f"[red]스크립트 파일 삭제 중: {selected_file['name']}[/]", total=None
            )

            # GitHub API를 통해 파일 정보 가져오기
            args = ["api", f"/repos/{owner}/{repo_name}/contents/{selected_file['path']}"]
            stdout, _ = run_gh_command(args)

            if stdout:
                file_data = json.loads(stdout)
                sha = file_data.get("sha")

                if sha:
                    # GitHub API를 통해 파일 삭제
                    delete_args = [
                        "api",
                        f"/repos/{owner}/{repo_name}/contents/{selected_file['path']}",
                        "--method",
                        "DELETE",
                        "-f",
                        f"message=Delete script: {selected_file['name']}",
                        "-f",
                        f"sha={sha}",
                        "-f",
                        "branch=main",
                    ]
                    delete_stdout, delete_stderr = run_gh_command(delete_args)

                    if delete_stdout and not delete_stderr:
                        console.print(
                            f"[success]스크립트 파일 [bold]{selected_file['name']}[/]이(가) 성공적으로 삭제되었습니다![/]"
                        )
                        return True
                    else:
                        console.print(
                            f"[error]스크립트 파일 삭제 실패:[/] {delete_stderr or '알 수 없는 오류'}"
                        )

    except Exception as e:
        console.print(f"[error]스크립트 파일 삭제 중 오류 발생:[/] {str(e)}")

    return False


def handle_delete_selection(
    current_files: List[Dict], start_idx: int, choice: str, owner: str, repo_name: str
) -> Tuple[bool, Optional[List[Dict]]]:
    """스크립트 삭제 선택을 처리합니다.

    Args:
        current_files: 현재 페이지의 파일 목록
        start_idx: 현재 페이지의 시작 인덱스
        choice: 사용자 선택
        owner: 레포지토리 소유자
        repo_name: 레포지토리 이름

    Returns:
        Tuple[bool, Optional[List[Dict]]]: (프로그램 종료 여부, 업데이트된 파일 목록)
    """
    if not choice.isdigit():
        return False, None

    idx = int(choice)
    if 1 <= idx <= len(current_files):
        file_idx = start_idx + idx - 1
        selected_file = current_files[file_idx]

        # 삭제 확인
        if (
            not Prompt.ask(
                f"[bold red]정말로 {selected_file['name']} 파일을 삭제하시겠습니까?[/]",
                choices=["y", "n"],
                default="n",
            )
            == "y"
        ):
            return False, None

        if delete_script_file(owner, repo_name, selected_file):
            # 파일 목록 업데이트
            updated_files = list_archive_script_files(repo_name, owner)
            return True, updated_files

    else:
        console.print("[error]잘못된 선택입니다. 다시 시도하세요.[/]")
        import time

        time.sleep(1)

    return False, None


def display_delete_menu(
    current_files: List[Dict], current_page: int, total_pages: int, repo_name: str
) -> None:
    """스크립트 삭제 메뉴를 표시합니다.

    Args:
        current_files: 현재 페이지의 파일 목록
        current_page: 현재 페이지 번호
        total_pages: 전체 페이지 수
        repo_name: 레포지토리 이름
    """
    console.clear()
    console.print(
        Panel(
            f"[bold]{repo_name}[/] 레포지토리의 스크립트 파일 목록 (페이지 {current_page + 1}/{total_pages})",
            border_style="red",
        )
    )

    # 테이블 생성
    table = Table(show_header=True)
    table.add_column("#", style="red", justify="right")
    table.add_column("파일명", style="green")
    table.add_column("경로", style="dim")

    # 파일 목록 표시
    for i, file in enumerate(current_files, 1):
        table.add_row(str(i), file["name"], file["path"])

    console.print(table)

    # 안내 메시지
    console.print("\n[bold]명령어:[/]")
    console.print(" 1-5: 파일 선택")
    if total_pages > 1:
        console.print(" n: 다음 페이지")
        console.print(" p: 이전 페이지")
    console.print(" q: 종료")


@script_group.command(name="delete")
def delete_script() -> None:
    """아카이브 레포지토리의 [bold red]스크립트를 삭제[/]합니다.

    기본 아카이브 레포지토리의 scripts/ 폴더에서 스크립트를 선택하여 삭제합니다.
    """
    check_gh_installed()

    # 기본 아카이브 레포지토리 찾기
    found, repo_name, owner = find_default_archive_repo()
    if not found or repo_name is None or owner is None:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        console.print("먼저 make-fown-archive 명령어로 기본 아카이브 레포지토리를 생성하세요.")
        return

    # 스크립트 파일 목록 가져오기
    try:
        files = list_archive_script_files(repo_name, owner)
        if not files:
            console.print(
                f"[warning][bold]{repo_name}[/] 레포지토리의 scripts/ 폴더에 스크립트 파일이 없습니다.[/]"
            )
            return
    except ValueError as e:
        console.print(f"[error]{str(e)}[/]")
        return

    # 페이지네이션 설정
    page_size = 5
    current_page = 0
    total_pages = (len(files) + page_size - 1) // page_size

    while True:
        # 현재 페이지에 표시할 파일 목록
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(files))
        current_files = files[start_idx:end_idx]

        # 메뉴 표시
        display_delete_menu(current_files, current_page, total_pages, repo_name)

        # 사용자 입력 처리
        choice = Prompt.ask("선택").strip().lower()

        if choice == "q":
            return
        elif choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        else:
            success, updated_files = handle_delete_selection(
                current_files, start_idx, choice, owner, repo_name
            )
            if success:
                if not updated_files:
                    return
                files = updated_files
                total_pages = (len(files) + page_size - 1) // page_size
                current_page = min(current_page, total_pages - 1)


def download_script_file(owner: str, repo_name: str, selected_file: Dict[str, str]) -> bool:
    """스크립트 파일을 다운로드하고 저장합니다.

    Args:
        owner: 레포지토리 소유자
        repo_name: 레포지토리 이름
        selected_file: 선택된 파일 정보

    Returns:
        bool: 다운로드 성공 여부
    """
    try:
        # GitHub API를 통해 파일 내용 가져오기
        args = ["api", f"/repos/{owner}/{repo_name}/contents/{selected_file['path']}"]
        stdout, _ = run_gh_command(args)

        if not stdout:
            return False

        # base64로 인코딩된 내용을 디코딩
        import base64

        content_data = json.loads(stdout)
        if "content" not in content_data:
            return False

        content = base64.b64decode(content_data["content"]).decode("utf-8")

        # 현재 경로에 파일 저장
        file_name = selected_file["name"]
        target_path = os.path.join(os.getcwd(), file_name)

        # 파일이 이미 존재하는 경우 확인
        if os.path.exists(target_path):
            if (
                not Prompt.ask(
                    f"[bold yellow]파일 '{file_name}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?[/]",
                    choices=["y", "n"],
                    default="n",
                )
                == "y"
            ):
                console.print("[info]다운로드가 취소되었습니다.[/]")
                return False

        # 파일 저장
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 실행 권한 부여 (.sh 파일인 경우)
        if file_name.endswith(".sh"):
            try:
                os.chmod(target_path, 0o755)
            except Exception as e:
                console.print(f"[warning]실행 권한 부여 실패: {str(e)}[/]")

        console.print(
            f"[success]스크립트 파일 [bold]{file_name}[/]이(가) 성공적으로 다운로드되었습니다![/]"
        )
        console.print(f"[info]저장 위치: [dim]{target_path}[/][/]")
        return True

    except Exception as e:
        console.print(f"[error]스크립트 파일 다운로드 중 오류 발생:[/] {str(e)}")
        return False


def handle_script_selection(
    current_files: List[Dict], start_idx: int, choice: str, owner: str, repo_name: str
) -> bool:
    """스크립트 선택을 처리합니다.

    Args:
        current_files: 현재 페이지의 파일 목록
        start_idx: 현재 페이지의 시작 인덱스
        choice: 사용자 선택
        owner: 레포지토리 소유자
        repo_name: 레포지토리 이름

    Returns:
        bool: 프로그램 종료 여부
    """
    if not choice.isdigit():
        return False

    idx = int(choice)
    if 1 <= idx <= len(current_files):
        file_idx = start_idx + idx - 1
        selected_file = current_files[file_idx]
        if download_script_file(owner, repo_name, selected_file):
            return True
    else:
        console.print("[error]잘못된 선택입니다. 다시 시도하세요.[/]")
        import time

        time.sleep(1)

    return False


def display_script_menu(
    current_files: List[Dict], current_page: int, total_pages: int, repo_name: str
) -> None:
    """스크립트 메뉴를 표시합니다.

    Args:
        current_files: 현재 페이지의 파일 목록
        current_page: 현재 페이지 번호
        total_pages: 전체 페이지 수
        repo_name: 레포지토리 이름
    """
    console.clear()
    console.print(
        Panel(
            f"[bold]{repo_name}[/] 레포지토리의 스크립트 파일 목록 (페이지 {current_page + 1}/{total_pages})",
            border_style="cyan",
        )
    )

    # 테이블 생성
    table = Table(show_header=True)
    table.add_column("#", style="cyan", justify="right")
    table.add_column("파일명", style="green")
    table.add_column("경로", style="dim")

    # 파일 목록 표시
    for i, file in enumerate(current_files, 1):
        table.add_row(str(i), file["name"], file["path"])

    console.print(table)

    # 안내 메시지
    console.print("\n[bold]명령어:[/]")
    console.print(" 1-5: 파일 선택")
    if total_pages > 1:
        console.print(" n: 다음 페이지")
        console.print(" p: 이전 페이지")
    console.print(" q: 종료")


@script_group.command(name="load")
def load_script() -> None:
    """아카이브 레포지토리의 [bold green]스크립트를 다운로드[/]합니다.

    기본 아카이브 레포지토리의 scripts/ 폴더에서 스크립트를 선택하여 현재 경로에 다운로드합니다.
    """
    check_gh_installed()

    # 기본 아카이브 레포지토리 찾기
    found, repo_name, owner = find_default_archive_repo()
    if not found or repo_name is None or owner is None:
        console.print("[error]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
        console.print("먼저 make-fown-archive 명령어로 기본 아카이브 레포지토리를 생성하세요.")
        return

    # 스크립트 파일 목록 가져오기
    files = list_archive_script_files(repo_name, owner)
    if not files:
        console.print(
            f"[warning][bold]{repo_name}[/] 레포지토리의 scripts/ 폴더에 스크립트 파일이 없습니다.[/]"
        )
        console.print("scripts/ 폴더에 .py 또는 .sh 파일을 추가하세요.")
        return

    # 페이지네이션 설정
    page_size = 5
    current_page = 0
    total_pages = (len(files) + page_size - 1) // page_size

    while True:
        # 현재 페이지에 표시할 파일 목록
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(files))
        current_files = files[start_idx:end_idx]

        # 메뉴 표시
        display_script_menu(current_files, current_page, total_pages, repo_name)

        # 사용자 입력 처리
        choice = Prompt.ask("선택").strip().lower()

        if choice == "q":
            return
        elif choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        elif handle_script_selection(current_files, start_idx, choice, owner, repo_name):
            return

"""
레이블 관련 명령어 모듈
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from fown.cli.archive import get_user_repository_by_name
from fown.core.models.config import Config, Label, Repository
from fown.core.services.github import LabelService
from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url, run_gh_command

# 이 모듈은 향후 확장을 위해 준비되었습니다.
# 현재는 main.py에 구현된 레이블 명령어를 이 모듈로 이동할 수 있습니다.


@click.group(name="labels")
def labels_group():
    """[bold yellow]레이블[/] 관련 명령어

    GitHub 레포지토리의 레이블을 관리합니다.
    """
    pass


def check_github_auth() -> Optional[str]:
    """GitHub 인증 상태를 확인하고 사용자 이름을 반환합니다.

    Returns:
        Optional[str]: 인증된 사용자 이름 또는 None
    """
    from fown.cli.archive import get_github_username

    username = get_github_username()
    if not username:
        console.print("[error]GitHub 사용자 정보를 가져올 수 없습니다.[/]")
        console.print("GitHub CLI에 로그인되어 있는지 확인하세요: gh auth login")
        return None
    return username


def get_config_from_repo(username: str, repo_name: str) -> Optional[Dict]:
    """레포지토리의 .fown/config.yml 파일 내용을 가져옵니다.

    Args:
        username: GitHub 사용자 이름
        repo_name: 레포지토리 이름

    Returns:
        Optional[Dict]: 설정 내용 또는 None
    """
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

                return yaml.safe_load(content)
    except Exception:
        pass
    return None


def find_default_repo_from_list(username: str, repos: Dict) -> Tuple[bool, Optional[str]]:
    """레포지토리 목록에서 기본 레포지토리를 찾습니다.

    Args:
        username: GitHub 사용자 이름
        repos: 레포지토리 목록 정보

    Returns:
        Tuple[bool, Optional[str]]: (찾았는지 여부, 레포지토리 이름)
    """
    if repos["total_count"] == 0:
        console.print("[info]등록된 기본 레포지토리가 없습니다.[/]")
        return False, None

    if repos["total_count"] == 1:
        console.print(
            f"[info]레포지토리 [bold]{repos['items'][0]['name']}[/] 발견, 설정 확인 중...[/]"
        )
        return True, repos["items"][0]["name"]

    if repos["total_count"] > 1:
        try:
            for item in repos["items"]:
                config = get_config_from_repo(username, item["name"])
                if config and config.get("default_repository") is True:
                    console.print(f"[info]기본 레포지토리 [bold]{item['name']}[/] 발견![/]")
                    return True, item["name"]
        except Exception as e:
            console.print(f"[error]레포지토리 확인 실패:[/] {str(e)}")
            return False, None

    console.print("[info]기본 아카이브 레포지토리를 찾을 수 없습니다.[/]")
    return False, None


def find_default_archive_repo() -> Tuple[bool, Optional[str], Optional[str]]:
    """기본 아카이브 레포지토리를 찾습니다.

    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            (찾았는지 여부, 레포지토리 이름, 레포지토리 소유자)
    """
    try:
        # GitHub 인증 확인
        username = check_github_auth()
        if not username:
            return False, None, None

        # 레포지토리 검색
        repo = get_user_repository_by_name("fown-archive")
        if not repo:
            console.print("[info]등록된 기본 레포지토리가 없습니다.[/]")
            return False, None, None

        # 기본 레포지토리 찾기
        found, repo_name = find_default_repo_from_list(username, repo)
        if found and repo_name:
            return True, repo_name, username

        return False, None, None

    except Exception as e:
        console.print(f"[error]레포지토리 확인 실패:[/] {str(e)}")
        return False, None, None


def get_archive_labels_file(repo_name: str, owner: str) -> Optional[str]:
    """아카이브 레포지토리에서 레이블 파일 가져오기
    Args:
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
    Returns:
        Optional[str]: 임시 파일 경로 또는 None
    """
    try:
        # labels/default_labels.json 파일 확인
        try:
            args = ["api", f"/repos/{owner}/{repo_name}/contents/labels/default_labels.json"]
            stdout, _ = run_gh_command(args)

            if stdout:
                # base64로 인코딩된 내용을 디코딩
                import base64

                content_data = json.loads(stdout)
                if "content" in content_data:
                    content = base64.b64decode(content_data["content"]).decode("utf-8")
                    labels_data = json.loads(content)

                    # 임시 파일에 저장
                    import tempfile

                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
                    with open(temp_file.name, "w", encoding="utf-8") as f:
                        json.dump(labels_data, f, ensure_ascii=False, indent=2)

                    return temp_file.name
        except Exception as e:
            console.print(f"[warning]레이블 파일 가져오기 실패: {str(e)}[/]")

        return None
    except Exception as e:
        console.print(f"[error]레이블 파일 확인 실패:[/] {str(e)}")
        return None


def list_archive_label_files(repo_name: str, owner: str) -> List[Dict]:
    """아카이브 레포지토리의 labels 디렉토리에 있는 파일 목록 가져오기
    Args:
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
    Returns:
        List[Dict]: 파일 목록 (이름, 경로, 타입)
    """
    try:
        args = ["api", f"/repos/{owner}/{repo_name}/contents/labels"]
        stdout, _ = run_gh_command(args)

        if stdout:
            files_data = json.loads(stdout)
            return [
                {"name": item["name"], "path": item["path"], "type": item["type"]}
                for item in files_data
                if item["type"] == "file" and item["name"].endswith(".json")
            ]
        return []
    except Exception as e:
        console.print(f"[warning]레이블 파일 목록 가져오기 실패: {str(e)}[/]")
        return []


def get_label_file_content(repo_name: str, owner: str, file_path: str) -> Optional[str]:
    """아카이브 레포지토리에서 특정 레이블 파일 내용 가져오기
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
                labels_data = json.loads(content)

                # 임시 파일에 저장
                import tempfile

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
                with open(temp_file.name, "w", encoding="utf-8") as f:
                    json.dump(labels_data, f, ensure_ascii=False, indent=2)

                return temp_file.name
        return None
    except Exception as e:
        console.print(f"[error]레이블 파일 내용 가져오기 실패:[/] {str(e)}")
        return None


def show_label_files_menu(files: List[Dict], repo_name: str, owner: str) -> Optional[str]:
    """레이블 파일 선택 메뉴 표시
    Args:
        files: 파일 목록
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
    Returns:
        Optional[str]: 선택한 레이블 파일 경로 또는 None
    """
    if not files:
        console.print("[warning]사용 가능한 레이블 파일이 없습니다.[/]")
        return None

    page_size = 5
    current_page = 0
    total_pages = (len(files) + page_size - 1) // page_size

    while True:
        console.clear()
        console.print(
            Panel(
                f"[bold]{repo_name}[/] 레포지토리의 레이블 파일 목록 (페이지 {current_page + 1}/{total_pages})",
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

        # 파일 목록 표시
        for i, file in enumerate(current_files, 1):
            table.add_row(str(i), file["name"])

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
                return get_label_file_content(repo_name, owner, file_path)
            else:
                console.print("[error]잘못된 선택입니다. 다시 시도하세요.[/]")
                import time

                time.sleep(1)


def load_labels_from_json(file_path: str) -> List[Label]:
    """JSON 파일에서 레이블 목록 로드
    Args:
        file_path: JSON 파일 경로
    Returns:
        List[Label]: 레이블 목록
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Label.from_dict(item) for item in data]
    except Exception as e:
        console.print(f"[error]레이블 파일 로드 실패:[/] {str(e)}")
        return []


def load_labels_from_archive(
    repo_name: str, owner: str, show_menu: bool = False
) -> Tuple[List[Label], Optional[str]]:
    """아카이브 레포지토리에서 레이블을 로드합니다.

    Args:
        repo_name: 레포지토리 이름
        owner: 레포지토리 소유자
        show_menu: 레이블 파일 선택 메뉴 표시 여부

    Returns:
        Tuple[List[Label], Optional[str]]: (레이블 목록, 임시 파일 경로)
    """
    temp_file_path = None
    labels = []

    if show_menu:
        # 아카이브 레포지토리에서 레이블 파일 선택
        files = list_archive_label_files(repo_name, owner)
        if files:
            temp_file_path = show_label_files_menu(files, repo_name, owner)
            if temp_file_path:
                labels = load_labels_from_json(temp_file_path)
    else:
        # 기본 아카이브 레포지토리의 레이블 파일 사용
        temp_file_path = get_archive_labels_file(repo_name, owner)
        if temp_file_path:
            labels = load_labels_from_json(temp_file_path)

    return labels, temp_file_path


def load_labels_from_file(labels_file: str) -> List[Label]:
    """파일에서 레이블을 로드합니다.

    Args:
        labels_file: 레이블 파일 경로

    Returns:
        List[Label]: 레이블 목록
    """
    file_ext = Path(labels_file).suffix.lower()
    if file_ext == ".json":
        return load_labels_from_json(labels_file)
    return Config.load_labels(labels_file)


def apply_labels_to_repo(labels: List[Label], repo_full_name: str) -> int:
    """레포지토리에 레이블을 적용합니다.

    Args:
        labels: 레이블 목록
        repo_full_name: 레포지토리 전체 이름 (owner/repo)

    Returns:
        int: 성공적으로 적용된 레이블 수
    """
    success_count = 0
    with Progress() as progress:
        task = progress.add_task("[cyan]레이블 생성 중...[/]", total=len(labels))

        for label in labels:
            if label.name and label.color:
                if LabelService.create_label(label, repo_full_name):
                    success_count += 1
            else:
                console.print(f"[warning]name 또는 color가 없는 라벨 항목이 있습니다: {label}[/]")
            progress.update(task, advance=1)

    return success_count


@labels_group.command(name="sync")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.option(
    "--labels-file",
    "--file",
    "-f",
    default=None,
    help="Labels YAML/JSON 파일 경로 (alias: --file)",
)
@click.option(
    "--archive",
    is_flag=True,
    help="아카이브 레포지토리의 레이블 파일 사용",
)
@click.confirmation_option(
    prompt="모든 레이블을 삭제하고 새로운 레이블을 적용하시겠습니까?", help="확인 없이 실행합니다."
)
def sync_labels(repo_url: Optional[str], labels_file: Optional[str], archive: bool):
    """레이블을 [bold green]동기화[/]합니다.
    모든 레이블을 삭제하고 새로운 레이블을 적용합니다.
    파일이나 URL을 지정하지 않으면 기본 아카이브 레포지토리의 레이블을 사용합니다.
    기본 아카이브 레포지토리가 없으면 기본 레이블을 사용합니다.
    --archive 옵션을 사용하면 아카이브 레포지토리의 레이블 파일 목록에서 선택할 수 있습니다.
    """
    check_gh_installed()

    # 저장소 정보 가져오기
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)

    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]의 레이블을 동기화합니다...[/]")

    # 레이블 로드
    labels = []
    temp_file_path = None

    if labels_file:
        # 사용자가 지정한 파일 사용
        labels = load_labels_from_file(labels_file)
    elif archive:
        # 아카이브 레포지토리에서 레이블 파일 선택
        found, repo_name, owner = find_default_archive_repo()
        if found and repo_name and owner:  # None 체크 추가
            labels, temp_file_path = load_labels_from_archive(repo_name, owner, show_menu=True)
    else:
        # 기본 아카이브 레포지토리 확인
        found, repo_name, owner = find_default_archive_repo()
        if found and repo_name and owner:  # None 체크 추가
            labels, temp_file_path = load_labels_from_archive(repo_name, owner)

        # 기본 아카이브 레포지토리가 없거나 레이블 파일이 없으면 기본 레이블 사용
        if not labels:
            default_labels_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "default_config.yml"
            )
            labels = Config.load_labels(default_labels_file)

    if not labels:
        console.print("[error]레이블 정의를 찾을 수 없습니다.[/]")
        return

    console.print(f"[info]{len(labels)}개의 레이블 정의를 로드했습니다.[/]")

    try:
        # 기존 레이블 모두 삭제
        console.print("[info]기존 레이블을 모두 삭제합니다...[/]")
        LabelService.delete_all_labels(repo.full_name)

        # 새 레이블 생성
        console.print("[info]새 레이블을 생성합니다...[/]")
        success_count = apply_labels_to_repo(labels, repo.full_name)

        console.print(
            Panel(
                f"[success]{success_count}[/]/{len(labels)} 개의 레이블 동기화 완료",
                title="작업 완료",
                border_style="green",
            )
        )

    finally:
        # 임시 파일 삭제
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


@labels_group.command(name="clear-all")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.confirmation_option(
    prompt="모든 레이블을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다!",
    help="확인 없이 실행합니다.",
)
def clear_all_labels(repo_url: Optional[str]):
    """레이포지토리의 [bold red]모든 라벨을 삭제[/]합니다.

    [red]주의: 이 작업은 되돌릴 수 없습니다![/]
    """
    check_gh_installed()

    # 저장소 정보 가져오기
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)

    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]의 라벨을 삭제합니다...[/]")

    # 레이블 삭제 서비스 호출
    LabelService.delete_all_labels(repo.full_name)


@labels_group.command(name="apply")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.option(
    "--labels-file",
    "--file",
    "-f",
    default=lambda: os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "default_config.yml"
    ),
    show_default=True,
    help="Labels YAML 파일 경로 (alias: --file)",
)
def apply_labels(repo_url: Optional[str], labels_file: str):
    """레이블을 [bold green]일괄 생성/업데이트[/]합니다.

    YAML 파일에 정의된 레이블을 GitHub 레포지토리에 적용합니다.
    레이블이 이미 존재하면 건너뜁니다.
    """
    check_gh_installed()

    # 저장소 정보 가져오기
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)

    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]에 레이블을 적용합니다...[/]")

    # 레이블 설정 로드
    labels = Config.load_labels(labels_file)
    console.print(f"[info]{len(labels)}개의 레이블 정의를 로드했습니다.[/]")

    # 레이블 생성
    success_count = 0
    for label in labels:
        if label.name and label.color:
            if LabelService.create_label(label, repo.full_name):
                success_count += 1
        else:
            console.print(f"[warning]name 또는 color가 없는 라벨 항목이 있습니다: {label}[/]")

    console.print(
        Panel(
            f"[success]{success_count}[/]/{len(labels)} 개의 레이블 적용 완료",
            title="작업 완료",
            border_style="green",
        )
    )

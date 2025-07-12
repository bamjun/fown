"""
아카이브 관련 명령어 모듈
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import rich_click as click
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fown.core.models.config import Config, Label, Repository
from fown.core.services.github import LabelService
from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url, run_gh_command


def get_user_repository_by_name(repo_name: str) -> Optional[Dict]:
    """사용자의 레포지토리 중 이름으로 검색

    Args:
        repo_name: 레포지토리 이름 (부분 일치)

    Returns:
        Optional[Dict]: 레포지토리 정보 또는 None
    """
    try:
        # gh search repos 명령어로 검색
        args = [
            "search",
            "repos",
            repo_name,
            f"--owner={get_github_username()}",
            "--json",
            "name,description,visibility,updatedAt",
        ]
        stdout, _ = run_gh_command(args)

        if not stdout:
            return None

        # 검색 결과 파싱
        import json

        repos = json.loads(stdout)

        # 검색된 레포지토리 수 반환
        if not repos:
            return None

        return {"total_count": len(repos), "items": repos}

    except Exception as e:
        from fown.core.utils.file_io import console

        console.print(f"[error]레포지토리 검색 실패:[/] {str(e)}")
        return None


def get_user_repositories() -> List[Dict]:
    """사용자의 모든 레포지토리 목록 가져오기"""
    try:
        args = ["repo", "list", "--json", "name", "--limit", "1000"]
        stdout, _ = run_gh_command(args)

        if stdout:
            return json.loads(stdout)
        return []
    except Exception as e:
        console.print(f"[warning]레포지토리 목록 가져오기 실패: {str(e)}[/]")
        return []


def get_available_repo_name(base_name: str, existing_repos: Optional[List[Dict]] = None) -> str:
    """사용 가능한 레포지토리 이름 찾기
    Args:
        base_name: 기본 레포지토리 이름 (예: fown-archive)
        existing_repos: 이미 가져온 레포지토리 목록 (없으면 새로 가져옴)
    Returns:
        str: 사용 가능한 레포지토리 이름
    """
    console.print("[info]사용 가능한 레포지토리 이름 확인 중...[/]")

    # 레포지토리 목록 가져오기
    if existing_repos is None:
        existing_repos = get_user_repositories()

    existing_repo_names = {repo["name"] for repo in existing_repos}

    # fown-archive부터 fown-archive9까지 확인
    for i in range(10):  # 0부터 9까지 시도
        suffix = "" if i == 0 else str(i)
        repo_name = f"{base_name}{suffix}"

        if repo_name not in existing_repo_names:
            console.print(f"[info]사용 가능한 레포지토리 이름: [bold]{repo_name}[/][/]")
            return repo_name

    # 모든 이름이 사용 중인 경우 랜덤 숫자 추가
    import random

    repo_name = f"{base_name}{random.randint(10, 99)}"
    console.print(f"[info]사용 가능한 레포지토리 이름: [bold]{repo_name}[/][/]")
    return repo_name


def create_archive_repo(repo_name: str, description: str, is_public: bool = False) -> bool:
    """GitHub에 아카이브 레포지토리 생성
    Args:
        repo_name: 생성할 레포지토리 이름
        description: 레포지토리 설명
        is_public: 공개 레포지토리 여부 (기본값: 비공개)
    Returns:
        bool: 생성 성공 여부
    """
    try:
        args = ["repo", "create", repo_name, "--description", description]

        # 공개 레포지토리 옵션 추가
        if is_public:
            args.append("--public")
        else:
            args.append("--private")

        run_gh_command(args)
        visibility = "public" if is_public else "private"
        console.print(f"[success]✓[/] Created {visibility} repository: [bold]{repo_name}[/]")
        return True
    except Exception as e:
        console.print(f"[error]레포지토리 '{repo_name}' 생성 실패: {str(e)}[/]")
        return False


def get_github_username() -> Optional[str]:
    """현재 인증된 GitHub 사용자 이름 가져오기"""
    try:
        stdout, _ = run_gh_command(["auth", "status"])
        if not stdout:
            return None

        # 출력에서 계정 이름 찾기
        for line in stdout.split("\n"):
            if "github.com account" in line:
                # "✓ Logged in to github.com account bamjun (keyring)" 형식에서 추출
                parts = line.split("account")
                if len(parts) > 1:
                    username = parts[1].strip().split()[0].strip()
                    return username

        return None
    except Exception as e:
        console.print(f"[error]GitHub 사용자 정보 가져오기 실패:[/] {str(e)}")
        return None


def get_github_user_info() -> Optional[Dict]:
    """현재 인증된 GitHub 사용자 상세 정보 가져오기"""
    try:
        stdout, _ = run_gh_command(["api", "user", "--jq", "."])
        if stdout:
            return json.loads(stdout)
        return None
    except Exception as e:
        console.print(f"[warning]GitHub 사용자 상세 정보 가져오기 실패:[/] {str(e)}")
        return None


def create_fown_config_file(
    repo_owner: str, repo_name: str, labels: List[Label], is_default: bool = True
) -> bool:
    """아카이브 레포지토리에 .fown/config.yml 파일 생성
    Args:
        repo_owner: 레포지토리 소유자 이름
        repo_name: 레포지토리 이름
        labels: 레이블 목록
        is_default: 기본 설정 레포지토리 여부
    """
    try:
        # 사용자 정보 가져오기
        user_info = get_github_user_info() or {}
        user_name = user_info.get("name") or repo_owner
        user_email = user_info.get("email") or f"{repo_owner}@users.noreply.github.com"

        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            # .fown 디렉토리 생성
            fown_dir = temp_dir / ".fown"
            label_dir = temp_dir / "labels"
            script_dir = temp_dir / "scripts"
            fown_dir.mkdir(exist_ok=True)
            label_dir.mkdir(exist_ok=True)
            script_dir.mkdir(exist_ok=True)

            # 설정 파일 생성
            config_data = {
                "default_repository": is_default,  # 기본 설정 레포지토리 여부
                "created_at": datetime.now().isoformat(),
            }

            with open(script_dir / "hello_world.sh", "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n")
                f.write("echo 'Hello, World!'\n")

            with open(label_dir / "default_labels.json", "w", encoding="utf-8") as f:
                json.dump([label.to_dict() for label in labels], f, ensure_ascii=False, indent=2)

            with open(fown_dir / "config.yml", "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            # README.md 파일 생성
            with open(temp_dir / "README.md", "w", encoding="utf-8") as f:
                f.write(f"# {repo_name}\n\n")
                f.write("이 레포지토리는 Fown에서 설정 및 관리를 위한 아카이브 레포지토리입니다.\n")
                f.write(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if is_default:
                    f.write("**이 레포지토리는 기본 설정 레포지토리입니다.**\n\n")
                f.write("## 포함된 설정\n\n")
                f.write("- `.fown/config.yml` 파일\n")
                f.write("   - 아카이브 레포지토리의 설정 파일\n")
                f.write("- `.fown/labels/` 폴더\n")
                f.write("   - 아카이브 레포지토리의 레이블 파일\n")
                f.write("- `.fown/scripts/` 폴더\n")
                f.write("   - 아카이브 레포지토리의 스크립트 파일\n")

            # Git 초기화 및 커밋
            current_dir = os.getcwd()
            os.chdir(temp_dir)

            # Git 명령어 실행
            commands = [
                "git init",
                "git add .",
                f'git config --local user.email "{user_email}"',
                f'git config --local user.name "{user_name}"',
                'git commit -m "Initial commit with archived settings"',
                f"git remote add origin https://github.com/{repo_owner}/{repo_name}.git",
                "git push -u origin main",
            ]

            for cmd in commands:
                result = os.system(cmd)
                if result != 0:
                    console.print(f"[warning]명령어 실패: {cmd}[/]")

            # 원래 디렉토리로 돌아가기
            os.chdir(current_dir)

            return True
    except Exception as e:
        console.print(f"[error]설정 파일 생성 실패:[/] {str(e)}")
        return False


def check_existing_default_repo(
    username: str, base_name: str, existing_repos: Optional[List[Dict]] = None
) -> Tuple[bool, Optional[str]]:
    """사용자의 레포지토리 중 기본 아카이브 레포지토리가 있는지 확인
    fown-archive부터 fown-archive9까지의 레포지토리를 검사하여
    .fown/config.yml 파일에 default_repository: True가 설정된 레포지토리가 있는지 확인합니다.
    Args:
        username: GitHub 사용자 이름
        base_name: 기본 레포지토리 이름 (예: fown-archive)
        existing_repos: 이미 가져온 레포지토리 목록 (없으면 새로 가져옴)
    Returns:
        Tuple[bool, Optional[str]]: (기본 레포지토리 존재 여부, 기본 레포지토리 이름)
    """
    console.print("[info]기존 기본 레포지토리 검사 중...[/]")

    try:
        # 레포지토리 목록 가져오기
        if existing_repos is None:
            existing_repos = get_user_repositories()

        existing_repo_names = {repo["name"] for repo in existing_repos}

        # fown-archive부터 fown-archive9까지 중 존재하는 레포지토리만 확인
        for i in range(10):  # 0부터 9까지 시도
            suffix = "" if i == 0 else str(i)
            repo_name = f"{base_name}{suffix}"

            if repo_name not in existing_repo_names:
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
                        config = yaml.safe_load(content)

                        # default_repository 값 확인
                        if config and config.get("default_repository") is True:
                            console.print(f"[info]기본 레포지토리 [bold]{repo_name}[/] 발견![/]")
                            return True, repo_name
            except Exception:
                # config.yml 파일이 없거나 접근할 수 없는 경우 무시
                pass

        console.print("[info]기존 기본 레포지토리를 찾을 수 없습니다.[/]")
        return False, None
    except Exception as e:
        console.print(f"[error]레포지토리 확인 실패:[/] {str(e)}")
        return False, None


@click.command(name="make-fown-archive")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.option(
    "--archive-name",
    "-n",
    default="fown-archive",
    show_default=True,
    help="생성할 아카이브 레포지토리 이름",
)
@click.option(
    "--default",
    is_flag=True,
    default=True,
    help="이 레포지토리를 기본 설정 레포지토리로 지정합니다.",
)
@click.option(
    "--force",
    is_flag=True,
    help="기본 설정 레포지토리가 이미 있어도 강제로 생성합니다.",
)
@click.option(
    "--public",
    is_flag=True,
    help="아카이브 레포지토리를 공개로 설정합니다. 기본값은 비공개입니다.",
)
def make_archive(
    repo_url: Optional[str], archive_name: str, default: bool, force: bool, public: bool
):
    """저장소 설정을 [bold green]아카이브[/]합니다.
    현재 저장소의 설정을 새로운 GitHub 레포지토리에 아카이브합니다.
    기본 설정 레포지토리로 지정하려면 --default 옵션을 사용합니다.
    이미 기본 설정 레포지토리가 있는 경우 --force 옵션을 사용하여 강제로 생성할 수 있습니다.
    기본적으로 비공개 레포지토리로 생성되며, --public 옵션을 사용하여 공개 레포지토리로 설정할 수 있습니다.
    """
    check_gh_installed()

    # 저장소 정보 가져오기
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)

    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]의 설정을 아카이브합니다...[/]")

    # 현재 인증된 사용자 정보 가져오기
    current_user = get_github_username()
    if not current_user:
        console.print("[error]GitHub 사용자 정보를 가져올 수 없습니다.[/]")
        console.print("GitHub CLI에 로그인되어 있는지 확인하세요: gh auth login")
        return

    # 사용자의 레포지토리 목록 미리 가져오기 (API 호출 최소화)
    user_repos = get_user_repositories()

    # 기본 레포지토리 체크
    # --default 옵션이 지정되고 --force 옵션이 지정되지 않은 경우에만 체크
    if default and not force:
        has_default, default_repo = check_existing_default_repo(
            current_user, archive_name, user_repos
        )

        if has_default:
            console.print(
                Panel(
                    f"이미 기본 설정 레포지토리가 존재합니다: [bold]https://github.com/{current_user}/{default_repo}[/]\n"
                    "기존 레포지토리를 계속 사용하거나 --force 옵션을 사용하여 새로 생성하세요.",
                    title="경고",
                    border_style="yellow",
                )
            )
            return

    # 사용 가능한 레포지토리 이름 찾기
    repo_name = get_available_repo_name(archive_name, user_repos)

    # 아카이브 레포지토리 생성
    with Progress(
        SpinnerColumn(), TextColumn("[info]아카이브 레포지토리 생성 중...[/]"), transient=True
    ) as progress:
        progress.add_task("", total=None)
        success = create_archive_repo(
            repo_name, f"Archive of {repo.full_name} repository settings", is_public=public
        )

    if not success:
        console.print(
            Panel(
                "아카이브 레포지토리를 생성할 수 없습니다. 다른 이름을 시도해보세요.",
                title="오류",
                border_style="red",
            )
        )
        return

    # 레이블 정보 가져오기
    console.print("[info]레이블 정보 가져오는 중...[/]")
    labels = LabelService.get_all_labels(repo.full_name)

    # 설정 파일 생성 및 푸시
    with Progress(
        SpinnerColumn(), TextColumn("[info]설정 파일 생성 및 푸시 중...[/]"), transient=True
    ) as progress:
        progress.add_task("", total=None)
        success = create_fown_config_file(current_user, repo_name, labels, is_default=default)

    if not success:
        console.print(
            Panel("설정 파일을 생성하는 데 실패했습니다.", title="오류", border_style="red")
        )
        return

    console.print(
        Panel(
            f"아카이브가 생성되었습니다: [bold]https://github.com/{current_user}/{repo_name}[/]"
            + (
                "\n이 레포지토리는 [bold]기본 설정 레포지토리[/]로 지정되었습니다."
                if default
                else ""
            ),
            title="아카이브 완료",
            border_style="green",
        )
    )

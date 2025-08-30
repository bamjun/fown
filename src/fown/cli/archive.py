"""
아카이브 관련 명령어 모듈
"""

import base64
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import rich_click as click
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fown.core.models.config import Label
from fown.core.services.github import LabelService
from fown.core.utils.file_io import console, make_github_api_request


def get_github_username() -> Optional[str]:
    """현재 인증된 GitHub 사용자 이름 가져오기"""
    try:
        user_data = make_github_api_request("GET", "user")
        # 명시적 타입 체크 추가
        if isinstance(user_data, dict):
            return user_data.get("login")
        return None
    except SystemExit:
        return None


def get_user_repositories() -> List[Dict]:
    """사용자의 모든 레포지토리 목록 가져오기"""
    try:
        repos = make_github_api_request(
            "GET", "user/repos", params={"per_page": 100, "type": "owner"}
        )
        # 명시적 타입 체크 추가
        return repos if isinstance(repos, list) else []
    except SystemExit:
        return []


def get_available_repo_name(base_name: str, existing_repos: Optional[List[Dict]] = None) -> str:
    """사용 가능한 레포지토리 이름 찾기"""
    console.print("[info]사용 가능한 레포지토리 이름 확인 중...[/]")
    if existing_repos is None:
        existing_repos = get_user_repositories()
    existing_repo_names = {repo["name"] for repo in existing_repos}

    for i in range(10):
        suffix = "" if i == 0 else str(i)
        repo_name = f"{base_name}{suffix}"
        if repo_name not in existing_repo_names:
            console.print(f"[info]사용 가능한 레포지토리 이름: [bold]{repo_name}[/][/]")
            return repo_name

    import random

    repo_name = f"{base_name}{random.randint(10, 99)}"
    console.print(f"[info]사용 가능한 레포지토리 이름: [bold]{repo_name}[/][/]")
    return repo_name


def create_archive_repo(repo_name: str, description: str, is_public: bool = False) -> bool:
    """GitHub에 아카이브 레포지토리 생성"""
    try:
        data = {
            "name": repo_name,
            "description": description,
            "private": not is_public,
        }
        make_github_api_request("POST", "user/repos", data=data)
        visibility = "public" if is_public else "private"
        console.print(f"[success]✓[/] Created {visibility} repository: [bold]{repo_name}[/]")
        return True
    except SystemExit:
        console.print(f"[error]레포지토리 '{repo_name}' 생성 실패[/]")
        return False


def create_file_in_repo(owner: str, repo_name: str, file_path: str, content: str, message: str):
    """Helper to create a single file in a repository"""
    endpoint = f"repos/{owner}/{repo_name}/contents/{file_path}"
    data = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    make_github_api_request("PUT", endpoint, data=data)


def create_fown_config_files(
    repo_owner: str, repo_name: str, labels: List[Label], is_default: bool = True
) -> bool:
    """아카이브 레포지토리에 설정 파일들 생성"""
    try:
        # 1. README.md
        readme_content = (
            f"# {repo_name}\n\n"
            "이 레포지토리는 Fown에서 설정 및 관리를 위한 아카이브 레포지토리입니다.\n"
            f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        if is_default:
            readme_content += "**이 레포지토리는 기본 설정 레포지토리입니다.**\n\n"
        readme_content += (
            "## 포함된 설정\n\n"
            "- `.fown/config.yml`: 아카이브 레포지토리의 설정 파일\n"
            "- `labels/`: 레이블 폴더\n"
            "- `labels/default_labels.json`: 기본 레이블 템플릿\n"
            "- `scripts/`: 스크립트 폴더\n"
            "- `files/`: 파일 폴더\n"
        )
        create_file_in_repo(
            repo_owner, repo_name, "README.md", readme_content, "Initial commit: Add README.md"
        )

        # 2. .fown/config.yml
        config_data = {
            "default_repository": is_default,
            "created_at": datetime.now().isoformat(),
        }
        config_content = yaml.dump(config_data, default_flow_style=False, allow_unicode=True)
        create_file_in_repo(
            repo_owner, repo_name, ".fown/config.yml", config_content, "Create fown config"
        )

        # 3. labels/default_labels.json
        labels_content = json.dumps(
            [label.to_dict() for label in labels], ensure_ascii=False, indent=2
        )
        create_file_in_repo(
            repo_owner,
            repo_name,
            "labels/default_labels.json",
            labels_content,
            "Add default labels",
        )

        # 4. scripts/hello_world.sh
        script_content = "#!/bin/bash\necho 'Hello, World!'\n"
        create_file_in_repo(
            repo_owner, repo_name, "scripts/hello_world.sh", script_content, "Add example script"
        )

        return True
    except SystemExit as e:
        console.print(f"[error]설정 파일 생성 실패:[/] {e}")
        return False


def check_existing_default_repo(
    username: str, base_name: str, existing_repos: Optional[List[Dict]] = None
) -> Tuple[bool, Optional[str]]:
    """기본 아카이브 레포지토리 확인"""
    console.print("[info]기존 기본 레포지토리 검사 중...[/]")
    if existing_repos is None:
        existing_repos = get_user_repositories()
    existing_repo_names = {repo["name"] for repo in existing_repos}

    for i in range(10):
        suffix = "" if i == 0 else str(i)
        repo_name = f"{base_name}{suffix}"
        if repo_name not in existing_repo_names:
            continue

        console.print(f"[info]레포지토리 [bold]{repo_name}[/] 발견, 설정 확인 중...[/]")
        try:
            endpoint = f"repos/{username}/{repo_name}/contents/.fown/config.yml"
            config_data = make_github_api_request("GET", endpoint)
            # 명시적 타입 체크 추가
            if isinstance(config_data, dict) and "content" in config_data:
                content = base64.b64decode(config_data["content"]).decode("utf-8")
                config = yaml.safe_load(content)
                if config and config.get("default_repository") is True:
                    console.print(f"[info]기본 레포지토리 [bold]{repo_name}[/] 발견![/]")
                    return True, repo_name
        except SystemExit:
            continue
    console.print("[info]기존 기본 레포지토리를 찾을 수 없습니다.[/]")
    return False, None


@click.command(name="make-fown-archive")
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
def make_archive(archive_name: str, default: bool, force: bool, public: bool):
    """저장소 설정을 [bold green]아카이브[/]합니다."""
    current_user = get_github_username()
    if not current_user:
        return

    user_repos = get_user_repositories()

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

    repo_name = get_available_repo_name(archive_name, user_repos)

    with Progress(
        SpinnerColumn(), TextColumn("[info]아카이브 레포지토리 생성 중...[/]"), transient=True
    ) as progress:
        progress.add_task("", total=None)
        success = create_archive_repo(repo_name, "Fown archive repository", is_public=public)

    if not success:
        return

    # For simplicity, we'll create a default set of labels for the new archive repo.
    # In a real scenario, you might want to fetch them from the current repo.
    labels = [
        Label(name="bug", color="d73a4a", description="Something isn't working"),
        Label(
            name="documentation",
            color="0075ca",
            description="Improvements or additions to documentation",
        ),
    ]

    with Progress(
        SpinnerColumn(), TextColumn("[info]설정 파일 생성 및 푸시 중...[/]"), transient=True
    ) as progress:
        progress.add_task("", total=None)
        success = create_fown_config_files(current_user, repo_name, labels, is_default=default)

    if not success:
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

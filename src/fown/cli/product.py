"""
프로젝트 관련 명령어 모듈
"""

import os
from typing import Optional

import rich_click as click
from rich.panel import Panel

from fown.core.models.config import Config, Repository
from fown.core.services.github import ProjectService
from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url


@click.group(name="projects")
def projects_group():
    """[bold blue]프로젝트[/] 관련 명령어

    GitHub 레포지토리의 프로젝트를 관리합니다.
    """
    pass


@projects_group.command(name="sync")
@click.option(
    "--repo-url", required=True, help="GitHub Repository URL (예: https://github.com/OWNER/REPO)"
)
@click.option(
    "--config",
    "-c",
    "config_file",
    default=lambda: os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "default_config.yml"
    ),
    show_default=True,
    help="Projects YAML 파일 경로",
)
def sync_projects(repo_url: str, config_file: str):
    """프로젝트 설정을 [bold green]동기화[/]합니다.

    YAML 파일에 정의된 프로젝트를 GitHub 레포지토리에 생성합니다.
    프로젝트가 이미 존재하면 건너뜁니다.
    """
    check_gh_installed()

    # 저장소 정보 가져오기
    repo = Repository.from_url(repo_url)

    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]의 프로젝트를 동기화합니다...[/]")

    # 프로젝트 설정 로드
    projects = Config.load_projects(config_file)
    console.print(f"[info]{len(projects)}개의 프로젝트 정의를 로드했습니다.[/]")

    # 프로젝트 동기화
    result = ProjectService.sync_projects(projects, repo.full_name)

    console.print(
        Panel(
            f"[green]{result['created']}[/]개 생성, [yellow]{result['skipped']}[/]개 건너뜀",
            title="프로젝트 동기화 완료",
            border_style="green",
        )
    )

"""
fown CLI 메인 엔트리포인트
"""
import os
from typing import Optional

import rich_click as click
from rich.markdown import Markdown
from rich.panel import Panel

from fown import __version__
from fown.core.models.config import Config, Label, Project, Repository
from fown.core.services.github import LabelService, ProjectService
from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url

# rich-click 설정
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.STYLE_OPTION = "bold cyan"
click.rich_click.STYLE_ARGUMENT = "bold green"
click.rich_click.STYLE_COMMAND = "bold"
click.rich_click.STYLE_SWITCH = "bold blue"


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx, version):
    """
    [bold cyan]fown[/] - GitHub 레이블 및 프로젝트 관리 도구

    레이블과 프로젝트를 쉽게 관리할 수 있는 CLI 도구입니다.
    """
    if version:
        console.print(f"[bold cyan]fown[/] 버전 [green]{__version__}[/]")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group()
def labels():
    """[bold yellow]레이블[/] 관련 명령어

    GitHub 레포지토리의 레이블을 관리합니다.
    """
    pass


@labels.command(name="apply")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.option(
    "--labels-file",
    "--file",
    "-f",
    default=lambda: os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "default_config.yml"),
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
    
    console.print(Panel(
        f"[success]{success_count}[/]/{len(labels)} 개의 레이블 적용 완료",
        title="작업 완료",
        border_style="green"
    ))


@labels.command(name="clear-all")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.confirmation_option(
    prompt="모든 레이블을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다!",
    help="확인 없이 실행합니다."
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


@main.group()
def projects():
    """[bold blue]프로젝트[/] 관련 명령어

    GitHub 레포지토리의 프로젝트를 관리합니다.
    """
    pass


@projects.command(name="sync")
@click.option(
    "--repo-url", 
    required=True, 
    help="GitHub Repository URL (예: https://github.com/OWNER/REPO)"
)
@click.option(
    "--config",
    "-c",
    "config_file",
    default=lambda: os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "default_config.yml"),
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
    
    console.print(Panel(
        f"[green]{result['created']}[/]개 생성, [yellow]{result['skipped']}[/]개 건너뜀",
        title="프로젝트 동기화 완료",
        border_style="green"
    ))


if __name__ == "__main__":
    main() 
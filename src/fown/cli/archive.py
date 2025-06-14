"""
아카이브 관련 명령어 모듈
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import rich_click as click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fown.core.models.config import Repository
from fown.core.utils.file_io import check_gh_installed, console, get_git_repo_url


@click.command(name="make-fown-archive")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
@click.option(
    "--output-dir",
    "-o",
    default="./fown-archives",
    show_default=True,
    help="아카이브 파일을 저장할 디렉토리 경로",
)
def make_archive(repo_url: Optional[str], output_dir: str):
    """저장소 설정을 [bold green]아카이브[/]합니다.

    현재 저장소의 설정 파일과 레이블, 프로젝트 정보를 아카이브 파일로 저장합니다.
    """
    check_gh_installed()
    
    # 저장소 정보 가져오기
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = Repository.from_url(repo_url)
    
    console.print(f"[info]레포지토리 [bold]{repo.full_name}[/]의 설정을 아카이브합니다...[/]")
    
    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 아카이브 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{repo.owner}_{repo.name}_{timestamp}"
    archive_path = output_path / archive_name
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[info]아카이브 생성 중...[/]"),
        transient=True
    ) as progress:
        progress.add_task("", total=None)
        
        # 아카이브 디렉토리 생성
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # TODO: 저장소 설정 파일 저장
        # TODO: 레이블 정보 저장
        # TODO: 프로젝트 정보 저장
    
    console.print(Panel(
        f"아카이브가 생성되었습니다: [bold]{archive_path}[/]",
        title="아카이브 완료",
        border_style="green"
    )) 
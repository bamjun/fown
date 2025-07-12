"""
파일 입출력 및 유틸리티 함수 모음
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple, Union

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

# Rich 설정
theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
    }
)
console = Console(theme=theme)


def check_gh_installed() -> None:
    """GitHub CLI가 설치되어 있는지 확인"""
    try:
        subprocess.run(
            ["gh", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception:
        console.print(
            Panel(
                "[error]GitHub CLI(gh)가 설치되어 있지 않습니다.[/]",
                title="오류",
                subtitle="설치 후 다시 시도하세요. site: https://cli.github.com/",
            )
        )
        raise SystemExit(1)


def load_yaml(file_path: str) -> Union[List, Dict, None]:
    """YAML 파일 로드"""
    if not os.path.exists(file_path):
        console.print(f"[error]{file_path} 파일이 존재하지 않습니다.[/]")
        raise SystemExit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_git_repo_url() -> str:
    """현재 디렉터리의 git origin URL 가져오기"""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        console.print(
            "[error]현재 디렉터리가 git 저장소가 아니거나 origin 원격을 찾을 수 없습니다.[/]"
        )
        raise SystemExit(1)


def extract_repo_info(repo_url: str) -> Tuple[str, str]:
    """GitHub 저장소 URL에서 소유자와 저장소 이름 추출"""
    match = re.match(
        r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?$", repo_url
    )
    if match:
        owner = match.group(1)
        repo = match.group(2)
        return owner, repo
    else:
        console.print(
            "[error]올바른 GitHub repo URL 형식이 아닙니다.[/]", "예: https://github.com/OWNER/REPO"
        )
        raise SystemExit(1)


def run_gh_command(args: List[str], check: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """GitHub CLI 명령 실행 및 결과 반환"""
    try:
        result = subprocess.run(
            ["gh"] + args,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout = result.stdout
        stderr = result.stderr

        # 바이너리 출력을 UTF-8로 디코딩 (errors='replace'로 잘못된 바이트 처리)
        stdout_text = stdout.decode("utf-8", errors="replace").strip() if stdout else None
        stderr_text = stderr.decode("utf-8", errors="replace").strip() if stderr else None

        return stdout_text, stderr_text
    except subprocess.CalledProcessError as e:
        if e.stderr:
            stderr_text = e.stderr.decode("utf-8", errors="replace")
            console.print(f"[error]명령 실행 실패:[/] {stderr_text}")
        raise

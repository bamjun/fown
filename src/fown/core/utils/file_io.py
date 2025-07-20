"""
파일 입출력 및 유틸리티 함수 모음
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple, Union

import requests
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

from fown.cli.auth import load_token

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


def make_github_api_request(
    method: str,
    endpoint: str,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    check_status: bool = True,
) -> Union[Dict, List, None]:
    """GitHub API에 인증된 요청을 보냅니다."""
    token = load_token()
    if not token:
        console.print("[error]로그인이 필요합니다. 'fown login start'를 실행하세요.[/]")
        raise SystemExit(1)

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/{endpoint}"

    try:
        response = requests.request(method, url, headers=headers, json=data, params=params)
        if check_status:
            response.raise_for_status()

        if response.status_code == 204:  # No Content
            return None

        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[error]인증 실패. 토큰이 유효하지 않거나 만료되었습니다. 'fown login start'로 다시 로그인하세요.[/]"
            )
        elif e.response.status_code == 404:
            console.print(f"[error]찾을 수 없음: {url}[/]")
        else:
            console.print(f"[error]API 요청 실패 ({e.response.status_code}): {e.response.text}[/]")
        raise SystemExit(1) from e
    except requests.exceptions.RequestException as e:
        console.print(f"[error]네트워크 오류: {e}[/]")
        raise SystemExit(1) from e


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

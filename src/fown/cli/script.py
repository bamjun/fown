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
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

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
                if item["type"] == "file" and (item["name"].endswith(".py") or item["name"].endswith(".sh"))
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
                temp_file_name = f"fown_script_{next(tempfile._get_candidate_names())}{os.path.splitext(file_name)[1]}"
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
        console.print(Panel(
            f"[bold]{repo_name}[/] 레포지토리의 스크립트 파일 목록 (페이지 {current_page + 1}/{total_pages})",
            border_style="cyan"
        ))
        
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
        
        if choice == 'q':
            return None
        elif choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
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


def run_script(script_path: str):
    """스크립트 실행
    
    Args:
        script_path: 스크립트 파일 경로
    """
    try:
        file_ext = os.path.splitext(script_path)[1].lower()
        script_name = os.path.basename(script_path)
        
        console.print(f"[info]스크립트 파일 경로: [dim]{script_path}[/][/]")
        
        if file_ext == '.py':
            # Python 스크립트 실행
            console.print(f"[info]Python 스크립트 실행 중: [bold]{script_name}[/][/]")
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        elif file_ext == '.sh':
            # Shell 스크립트 실행
            console.print(f"[info]Shell 스크립트 실행 중: [bold]{script_name}[/][/]")
            # Windows에서는 Git Bash 또는 WSL을 사용하여 실행
            if os.name == 'nt':
                # Git Bash 경로 확인
                git_bash_paths = [
                    "C:\\Program Files\\Git\\bin\\bash.exe",
                    "C:\\Program Files (x86)\\Git\\bin\\bash.exe"
                ]
                bash_path = None
                for path in git_bash_paths:
                    if os.path.exists(path):
                        bash_path = path
                        break
                
                if bash_path:
                    # Git Bash로 실행
                    result = subprocess.run([bash_path, script_path], capture_output=True, text=True)
                else:
                    # Git Bash가 없으면 WSL 시도
                    try:
                        result = subprocess.run(["wsl", "bash", script_path], capture_output=True, text=True)
                    except FileNotFoundError:
                        console.print("[error]Windows에서 bash를 찾을 수 없습니다. Git Bash 또는 WSL을 설치하세요.[/]")
                        return
            else:
                # Linux/Mac에서는 기본 bash 사용
                result = subprocess.run(['bash', script_path], capture_output=True, text=True)
        else:
            console.print(f"[error]지원하지 않는 스크립트 형식: {file_ext}[/]")
            return
            
        # 실행 결과 출력
        if result.returncode == 0:
            console.print(Panel(
                result.stdout,
                title="스크립트 실행 성공",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[error]에러 코드: {result.returncode}[/]\n\n{result.stderr}",
                title="스크립트 실행 실패",
                border_style="red"
            ))
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
        console.print(f"[warning][bold]{repo_name}[/] 레포지토리의 scripts/ 폴더에 스크립트 파일이 없습니다.[/]")
        console.print("scripts/ 폴더에 .py 또는 .sh 파일을 추가하세요.")
        return
        
    # 스크립트 파일 선택 메뉴 표시
    script_path = show_script_files_menu(files, repo_name, owner)
    if script_path:
        # 선택한 스크립트 실행
        run_script(script_path)

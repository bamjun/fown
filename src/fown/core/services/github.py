"""
GitHub API 서비스 로직 구현
"""

from typing import Dict, List, Optional

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from fown.core.models.config import Label, Project
from fown.core.utils.file_io import console, make_github_api_request


def get_github_username() -> Optional[str]:
    """GitHub 사용자 이름 가져오기"""
    try:
        user_data = make_github_api_request("GET", "user")
        # 명시적 타입 체크 추가
        if isinstance(user_data, dict):
            return user_data.get("login")
        return None
    except SystemExit:
        return None


def get_user_repositories() -> List[Dict]:
    """사용자의 모든 저장소 가져오기"""
    try:
        repos = make_github_api_request("GET", "user/repos", params={"per_page": 100})
        # 명시적 타입 체크 추가
        return repos if isinstance(repos, list) else []
    except SystemExit:
        return []


class LabelService:
    """GitHub 레이블 관련 서비스"""

    @staticmethod
    def create_label(label: Label, repo_name: str) -> bool:
        """레이블 생성"""
        try:
            endpoint = f"repos/{repo_name}/labels"
            data = {
                "name": label.name,
                "color": label.color.lstrip("#"),
                "description": label.description,
            }
            make_github_api_request("POST", endpoint, data=data)
            console.print(f"[success]✓[/] Created label: [bold]{label.name}[/]")
            return True
        except Exception:
            console.print(
                f"[warning]![/] Label '[bold]{label.name}[/]' already exists or error occurred."
            )
            return False

    @staticmethod
    def get_all_labels(repo_name: str) -> List[Label]:
        """저장소의 모든 레이블 조회"""
        try:
            with Progress(
                SpinnerColumn(), TextColumn("[info]레이블 목록 가져오는 중...[/]"), transient=True
            ) as progress:
                progress.add_task("", total=None)
                endpoint = f"repos/{repo_name}/labels"
                labels_data = make_github_api_request("GET", endpoint, params={"per_page": 100})

            # 명시적 타입 체크 추가
            if not isinstance(labels_data, list):
                return []

            return [Label.from_dict(item) for item in labels_data]
        except Exception as e:
            console.print(f"[error]레이블 목록 가져오기 실패:[/] {str(e)}")
            return []

    @staticmethod
    def delete_label(label_name: str, repo_name: str) -> bool:
        """레이블 삭제"""
        try:
            endpoint = f"repos/{repo_name}/labels/{label_name}"
            make_github_api_request("DELETE", endpoint)
            console.print(f"[success]✓[/] Deleted label: [bold]{label_name}[/]")
            return True
        except Exception as e:
            console.print(f"[error]레이블 삭제 실패 '{label_name}':[/] {str(e)}")
            return False

    @staticmethod
    def delete_all_labels(repo_name: str) -> int:
        """모든 레이블 삭제"""
        labels = LabelService.get_all_labels(repo_name)
        if not labels:
            console.print("[warning]레이블을 찾을 수 없습니다.[/]")
            return 0

        console.print(f"[info]{len(labels)}개의 레이블을 찾았습니다.[/]")

        with Progress() as progress:
            task = progress.add_task("[cyan]레이블 삭제 중...[/]", total=len(labels))
            success_count = 0

            for label in labels:
                if LabelService.delete_label(label.name, repo_name):
                    success_count += 1
                progress.update(task, advance=1)

        console.print(
            Panel(
                f"[success]{success_count}[/]/{len(labels)} 개의 레이블 삭제 완료",
                title="작업 완료",
                border_style="green",
            )
        )
        return success_count


class ProjectService:
    """GitHub 프로젝트 관련 서비스"""

    @staticmethod
    def get_all_projects(repo_name: str) -> List[Project]:
        """저장소의 모든 프로젝트 조회"""
        try:
            with Progress(
                SpinnerColumn(), TextColumn("[info]프로젝트 목록 가져오는 중...[/]"), transient=True
            ) as progress:
                progress.add_task("", total=None)
                owner, _ = repo_name.split("/")
                endpoint = f"users/{owner}/projects"
                projects_data = make_github_api_request("GET", endpoint, params={"per_page": 100})

            # 명시적 타입 체크 추가
            if not isinstance(projects_data, list):
                return []

            return [Project.from_dict(item) for item in projects_data]
        except Exception as e:
            console.print(f"[error]프로젝트 목록 가져오기 실패:[/] {str(e)}")
            return []

    @staticmethod
    def create_project(project: Project, repo_name: str) -> bool:
        """프로젝트 생성"""
        try:
            owner, _ = repo_name.split("/")
            endpoint = f"users/{owner}/projects"
            data = {"name": project.name, "body": project.description}
            make_github_api_request("POST", endpoint, data=data)
            console.print(f"[success]✓[/] Created project: [bold]{project.name}[/]")
            return True
        except Exception:
            console.print(f"[error]Project 생성 실패:[/] [bold]{project.name}[/]")
            return False

    @staticmethod
    def sync_projects(projects: List[Project], repo_name: str) -> Dict[str, int]:
        """프로젝트 동기화"""
        existing_projects = ProjectService.get_all_projects(repo_name)
        existing_names = [p.name for p in existing_projects]

        created = 0
        skipped = 0

        table = Table(title="프로젝트 동기화 결과")
        table.add_column("프로젝트", style="cyan")
        table.add_column("상태", style="green")

        for project in projects:
            if not project.name:
                console.print(f"[warning]name이 없는 프로젝트 항목: {project}[/]")
                continue

            if project.name in existing_names:
                table.add_row(project.name, "[yellow]이미 존재함[/]")
                skipped += 1
            else:
                if ProjectService.create_project(project, repo_name):
                    table.add_row(project.name, "[green]생성됨[/]")
                    created += 1
                else:
                    table.add_row(project.name, "[red]실패[/]")

        console.print(table)
        return {"created": created, "skipped": skipped}

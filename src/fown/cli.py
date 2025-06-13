import json
import os
import re
import subprocess

import click
import yaml

from fown import __version__


def check_gh_installed():
    try:
        subprocess.run(
            ["gh", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception:
        click.echo(
            "GitHub CLI(gh)가 설치되어 있지 않습니다. 설치 후 다시 시도하세요. site: https://cli.github.com/",
            err=True,
        )
        raise SystemExit(1)


def load_labels(labels_file):
    if not os.path.exists(labels_file):
        click.echo(f"{labels_file} 파일이 존재하지 않습니다.", err=True)
        raise SystemExit(1)
    with open(labels_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def load_config(config_file):
    if not os.path.exists(config_file):
        click.echo(f"{config_file} 파일이 존재하지 않습니다.", err=True)
        raise SystemExit(1)
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_existing_projects(repo):
    try:
        result = subprocess.run(
            ["gh", "project", "list", "--repo", repo, "--json", "name"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        data = json.loads(result.stdout)
        return [item.get("name") for item in data]
    except Exception:
        click.echo("프로젝트 목록 로딩 중 오류 발생, 생성만 시도합니다.", err=True)
        return []


def get_git_repo_url():
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
        click.echo(
            "현재 디렉터리가 git 저장소가 아니거나 origin 원격을 찾을 수 없습니다.", err=True
        )
        raise SystemExit(1)


def extract_repo_name(repo_url):
    match = re.match(
        r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?$", repo_url
    )
    if match:
        owner = match.group(1)
        repo = match.group(2)
        return f"{owner}/{repo}"
    else:
        click.echo(
            "올바른 GitHub repo URL 형식이 아닙니다. 예: https://github.com/OWNER/REPO", err=True
        )
        raise SystemExit(1)


def create_label(name, color, description, repo):
    try:
        subprocess.run(
            [
                "gh",
                "label",
                "create",
                name,
                "--color",
                color,
                "--description",
                description,
                "--repo",
                repo,
            ],
            check=True,
        )
        click.echo(f"[OK] Created label: {name}")
    except subprocess.CalledProcessError:
        click.echo(f"[SKIP] Label '{name}' already exists or error occurred.")


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx, version):
    """fown 명령어 그룹"""
    if version:
        click.echo(f"fown 버전 {__version__}")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group()
def labels():
    """Labels 관련 명령어"""
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
    default=lambda: os.path.join(os.path.dirname(__file__), "labels.yml"),
    show_default=True,
    help="Labels YAML 파일 경로 (alias: --file)",
)
def apply(repo_url, labels_file):
    """레이블을 일괄 생성/업데이트합니다."""
    check_gh_installed()
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = extract_repo_name(repo_url)
    labels = load_labels(labels_file)

    for label in labels:
        name = label.get("name")
        color = label.get("color")
        description = label.get("description", "")

        if name and color:
            create_label(name, color, description, repo)
        else:
            click.echo(f"[WARNING] name 또는 color가 없는 라벨 항목이 있습니다: {label}")


@labels.command(name="clear-all")
@click.option(
    "--repo-url",
    default=None,
    help="GitHub Repository URL. 지정하지 않으면 현재 디렉터리의 origin 원격을 사용합니다.",
)
def clear_all(repo_url):  # noqa: C901
    """레이포지토리의 모든 라벨을 삭제합니다."""
    check_gh_installed()
    if not repo_url:
        repo_url = get_git_repo_url()
    repo = extract_repo_name(repo_url)
    click.echo(f"[INFO] 레포지토리 {repo}의 라벨을 삭제합니다...")
    try:
        # 전체 라벨 조회 (JSON 형식)
        result = subprocess.run(
            ["gh", "label", "list", "--repo", repo, "--json", "name", "--limit", "1000"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout = result.stdout
        if stdout is None:
            click.echo("[ERROR] 라벨 목록을 가져올 수 없습니다.")
            return

        # 바이너리 출력을 UTF-8로 디코딩 (errors='replace'로 잘못된 바이트 처리)
        stdout_text = stdout.decode("utf-8", errors="replace").strip()

        if not stdout_text:
            click.echo("[WARNING] 라벨을 찾을 수 없습니다.")
            return

        try:
            labels = json.loads(stdout_text)
            click.echo(f"[INFO] {len(labels)}개의 라벨을 찾았습니다.")
        except json.JSONDecodeError as e:
            click.echo(f"[ERROR] JSON 파싱 오류: {str(e)}")
            click.echo(f"[DEBUG] 출력: {stdout_text[:100]}...")
            return
    except subprocess.CalledProcessError as e:
        click.echo(f"[ERROR] 라벨 목록 가져오기 실패: {e}", err=True)
        if e.stderr:
            error_text = e.stderr.decode("utf-8", errors="replace")
            click.echo(f"[DEBUG] 오류 출력: {error_text}", err=True)
        return

    for label in labels:
        name = label.get("name", "")
        if not name:
            click.echo("[WARNING] 이름 없는 라벨 항목 건너뜀")
            continue
        try:
            click.echo(f"[INFO] 라벨 삭제 중: {name}")
            subprocess.run(
                ["gh", "label", "delete", name, "--repo", repo, "--yes"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            click.echo(f"[OK] Deleted label: {name}")
        except subprocess.CalledProcessError as e:
            click.echo(f"[ERROR] 라벨 삭제 실패 '{name}': {e}")
            if e.stderr:
                click.echo(
                    f"[DEBUG] 오류 출력: {e.stderr.decode('utf-8', errors='replace')}", err=True
                )

    click.echo("[INFO] 라벨 삭제 작업 완료")


@main.group()
def projects():
    """Projects 관련 명령어"""
    pass


@projects.command(name="sync")
@click.option(
    "--repo-url", required=True, help="GitHub Repository URL (예: https://github.com/OWNER/REPO)"
)
@click.option(
    "--config",
    "-c",
    "config_file",
    default="project_config.yaml",
    show_default=True,
    help="Projects YAML 파일 경로",
)
def sync(repo_url, config_file):
    """프로젝트 설정을 동기화합니다."""
    check_gh_installed()
    repo = extract_repo_name(repo_url)
    cfg = load_config(config_file)
    existing = get_existing_projects(repo)
    for proj in cfg.get("projects", []):
        name = proj.get("name")
        description = proj.get("description", "")
        if not name:
            click.echo(f"[WARNING] name이 없는 프로젝트 항목: {proj}")
            continue
        if name in existing:
            click.echo(f"[SKIP] Project '{name}' 이미 존재합니다.")
        else:
            try:
                subprocess.run(
                    ["gh", "project", "create", name, "--description", description, "--repo", repo],
                    check=True,
                )
                click.echo(f"[OK] Created project: {name}")
            except subprocess.CalledProcessError:
                click.echo(f"[ERROR] Project 생성 실패: {name}")


if __name__ == "__main__":
    main()

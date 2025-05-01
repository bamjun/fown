import click
import subprocess
import yaml
import os
import re
import json


def check_gh_installed():
    try:
        subprocess.run(
            ["gh", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception:
        click.echo("GitHub CLI(gh)가 설치되어 있지 않습니다. 설치 후 다시 시도하세요.", err=True)
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
            text=True
        )
        data = json.loads(result.stdout)
        return [item.get("name") for item in data]
    except Exception:
        click.echo("프로젝트 목록 로딩 중 오류 발생, 생성만 시도합니다.", err=True)
        return []


def extract_repo_name(repo_url):
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)", repo_url)
    if match:
        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        return f"{owner}/{repo}"
    else:
        click.echo(
            "올바른 GitHub repo URL 형식이 아닙니다. 예: https://github.com/OWNER/REPO",
            err=True
        )
        raise SystemExit(1)


def create_label(name, color, description, repo):
    try:
        subprocess.run(
            ["gh", "label", "create", name, "--color", color, "--description", description, "--repo", repo],
            check=True
        )
        click.echo(f"[OK] Created label: {name}")
    except subprocess.CalledProcessError:
        click.echo(f"[SKIP] Label '{name}' already exists or error occurred.")


@click.group()
def main():
    """fown 명령어 그룹"""
    pass


@main.group()
def labels():
    """Labels 관련 명령어"""
    pass


@labels.command(name="apply")
@click.option(
    "--repo-url",
    required=True,
    help="GitHub Repository URL (예: https://github.com/OWNER/REPO)"
)
@click.option(
    "--labels-file", "--file", "-f",
    default=lambda: os.path.join(os.path.dirname(__file__), "labels.yml"),
    show_default=True,
    help="Labels YAML 파일 경로 (alias: --file)"
)
def apply(repo_url, labels_file):
    """레이블을 일괄 생성/업데이트합니다."""
    check_gh_installed()
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


@main.group()
def projects():
    """Projects 관련 명령어"""
    pass


@projects.command(name="sync")
@click.option(
    "--repo-url",
    required=True,
    help="GitHub Repository URL (예: https://github.com/OWNER/REPO)"
)
@click.option(
    "--config", "-c", "config_file", 
    default="project_config.yaml",
    show_default=True,
    help="Projects YAML 파일 경로"
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
                    check=True
                )
                click.echo(f"[OK] Created project: {name}")
            except subprocess.CalledProcessError:
                click.echo(f"[ERROR] Project 생성 실패: {name}")


if __name__ == '__main__':
    main() 
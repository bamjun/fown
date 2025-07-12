"""
fown CLI 메인 엔트리포인트
"""

import rich_click as click

from fown import __version__
from fown.cli.archive import make_archive
from fown.cli.label import labels_group
from fown.cli.product import projects_group
from fown.cli.script import script_group
from fown.core.utils.file_io import console

# rich-click 설정
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = False  # Markdown 대신 Rich 마크업만 사용
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
    """[bold cyan]fown[/] - GitHub 레이블 및 프로젝트 관리 도구

    레이블과 프로젝트를 쉽게 관리할 수 있는 CLI 도구입니다.
    """
    if version:
        console.print(f"[bold cyan]fown[/] 버전 [green]{__version__}[/]")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# 명령어 추가
main.add_command(make_archive)
main.add_command(labels_group)
main.add_command(projects_group)
main.add_command(script_group)


if __name__ == "__main__":
    main()

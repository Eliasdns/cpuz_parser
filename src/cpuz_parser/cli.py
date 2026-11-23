"""Command-line interface for cpuz_parser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .features import FEATURE_RICH


if FEATURE_RICH:
    import rich_click as click

    click.rich_click.TEXT_MARKUP = 'markdown'
    click.rich_click.SHOW_ARGUMENTS = True
    click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
    click.rich_click.STYLE_OPTIONS_PANEL_BORDER = 'cyan'
    click.rich_click.STYLE_COMMANDS_PANEL_BORDER = 'green'
else:
    import click  # type: ignore[no-redef]

from . import exporters
from .parsers import CpuzTxtParser


FORMAT_EXTENSION_MAP = {
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.xml': 'xml',
    '.txt': 'plain',
}


@click.command(name='cpuz_parser', context_settings={'help_option_names': ['-h', '--help']})
@click.argument(
    'report_file',
    type=click.Path(allow_dash=True, path_type=str),
    required=True,
)
@click.option(
    '-c',
    '--config',
    'config_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help='Path to JSON configuration file with RAM frequency mappings.',
)
@click.option(
    '-f',
    '--format',
    'output_format',
    type=click.Choice(['plain', 'rich', 'json', 'yaml', 'toml', 'xml'], case_sensitive=False),
    default=None,
    help="Output format (default: 'rich' if available and writing to stdout, otherwise 'plain').",
)
@click.option(
    '-o',
    '--output',
    'output_file',
    type=click.Path(allow_dash=True, path_type=str),
    default='-',
    show_default=True,
    help="Destination file path, or '-' to print to stdout.",
)
@click.version_option(package_name='cpuz_parser')
def main(
    report_file: str,
    config_file: Path | None,
    output_format: str | None,
    output_file: str,
) -> int:
    """Parse CPU-Z TXT reports and export structured hardware data."""
    # Parse configuration strictly if provided; otherwise default to empty dict
    ram_translate: dict[str, str] = {}
    if config_file is not None:
        with open(config_file, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            ram_translate = cfg.get('ram_freqs_single_mul2_to_friendly', {})

    # Instantiate parser from stdin ('-') or file path
    if report_file == '-':
        parser = CpuzTxtParser(sys.stdin.buffer, ram_freq_translate=ram_translate)
    else:
        path = Path(report_file)
        if not path.is_file():
            raise click.BadParameter(f"File '{report_file}' does not exist.", param_hint="'REPORT_FILE'")
        parser = CpuzTxtParser(str(path), ram_freq_translate=ram_translate)

    # Deduce output format
    if output_format is None:
        if output_file != '-' and Path(output_file).suffix.lower() in FORMAT_EXTENSION_MAP:
            output_format = FORMAT_EXTENSION_MAP[Path(output_file).suffix.lower()]
        else:
            output_format = 'rich' if (FEATURE_RICH and output_file == '-') else 'plain'
    else:
        output_format = output_format.lower()

    # Route to exporters via match/case
    try:
        match output_format:
            case 'rich':
                if output_file == '-':
                    exporters.to_rich(parser)
                    return 0
                content = exporters.to_plain(parser)
            case 'plain':
                content = exporters.to_plain(parser)
            case 'json':
                content = exporters.to_json(parser)
            case 'yaml':
                content = exporters.to_yaml(parser)
            case 'toml':
                content = exporters.to_toml(parser)
            case 'xml':
                content = exporters.to_xml(parser)
            case _:
                raise click.UsageError(f"Unsupported format: '{output_format}'")
    except ImportError as e:
        raise click.UsageError(str(e)) from e

    # Output to stdout ('-') or file
    if output_file == '-':
        if output_format == 'json' and FEATURE_RICH:
            from rich.console import Console

            Console().print_json(content)
        else:
            click.echo(content, nl=output_format not in ('plain',))
    else:
        Path(output_file).write_text(content, encoding='utf-8')
        if FEATURE_RICH:
            from rich.console import Console

            Console().print(f'[bold green]Report successfully exported to:[/bold green] {output_file}')
        else:
            click.echo(f'Report successfully exported to: {output_file}')

    return 0

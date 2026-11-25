"""Command-line interface for cpuz_parser."""

from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .features import FEATURE_RICH, require_rich_feature


if FEATURE_RICH:
    import rich_click as click

    click.rich_click.THEME = "dracula-modern"
    click.rich_click.TEXT_MARKUP = 'markdown'
    click.rich_click.DELIMITER_SLASH = ',\n '
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


@dataclass(frozen=True)
class CliConfig:
    """Validated configuration loaded from a JSON config file."""

    ram_freqs_single_mul2_to_friendly: dict[str, str] | None = None
    auto_combine_slots: bool | None = None


def load_config(config_file: Path) -> CliConfig:
    """Load and validate a JSON configuration file.

    Validates the supported options:
    - ``ram_freqs_single_mul2_to_friendly``: mapping of ``str`` to ``str``.
    - ``auto_combine_slots``: strict ``bool``.

    Raises ``click.ClickException`` (exit code 1) if the file is malformed.
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Malformed JSON in config file '{config_file}': {e.msg}") from e

    if not isinstance(cfg, dict):
        raise click.ClickException(f"Config file '{config_file}' must contain a JSON object.")

    ram_freq_translate: dict[str, str] | None = cfg.get('ram_freqs_single_mul2_to_friendly')
    if 'ram_freqs_single_mul2_to_friendly' in cfg and (
        not isinstance(ram_freq_translate, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in ram_freq_translate.items())
    ):
        raise click.ClickException(
            "Config key 'ram_freqs_single_mul2_to_friendly' must be an object mapping strings to strings."
        )

    auto_combine_slots: bool | None = cfg.get('auto_combine_slots')
    if 'auto_combine_slots' in cfg and not isinstance(auto_combine_slots, bool):
        raise click.ClickException("Config key 'auto_combine_slots' must be a boolean (true/false).")

    return CliConfig(
        ram_freqs_single_mul2_to_friendly=ram_freq_translate,
        auto_combine_slots=auto_combine_slots,
    )


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
    help='Path to JSON configuration file.',
)
@click.option(
    '--auto-combine-slots/--no-auto-combine-slots',
    'auto_combine_slots',
    default=None,
    help='Merge each RAM slot into a single string and count duplicates. Overrides `--config` (default: True).',
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
    auto_combine_slots: bool | None,
    output_format: str | None,
    output_file: str,
) -> int:
    """Parse CPU-Z TXT reports and export structured hardware data."""
    config = load_config(config_file) if config_file is not None else CliConfig()

    if auto_combine_slots is not None:
        effective_auto_combine = auto_combine_slots
    elif config.auto_combine_slots is not None:
        effective_auto_combine = config.auto_combine_slots
    else:
        effective_auto_combine = True

    # Instantiate parser from stdin ('-') or file path
    if report_file == '-':
        parser = CpuzTxtParser(
            sys.stdin.buffer,
            ram_freq_translate=config.ram_freqs_single_mul2_to_friendly,
            auto_combine_slots=effective_auto_combine,
        )
    else:
        path = Path(report_file)
        if not path.is_file():
            raise click.BadParameter(f"File '{report_file}' does not exist.", param_hint="'REPORT_FILE'")
        parser = CpuzTxtParser(
            str(path),
            ram_freq_translate=config.ram_freqs_single_mul2_to_friendly,
            auto_combine_slots=effective_auto_combine,
        )

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
                else:
                    require_rich_feature()
                    from rich.console import Console

                    buf = io.StringIO()
                    exporters.to_rich(parser, console=Console(file=buf, no_color=True, width=120))
                    content = buf.getvalue()
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

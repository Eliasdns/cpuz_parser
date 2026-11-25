"""Unit tests for the cpuz_parser CLI, configuration loading, and format routing."""

from __future__ import annotations

import importlib
import json
import runpy
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import click
import pytest

import cpuz_parser
import cpuz_parser.cli
from cpuz_parser.cli import CliConfig, load_config, main
from cpuz_parser.features import FEATURE_TOML, FEATURE_YAML


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.unit


def _write_config(
    directory: Path,
    content: str | dict[str, Any],
    filename: str = 'config.json',
) -> Path:
    """Write a JSON mapping or raw text config file into a temporary directory."""
    config_path = directory / filename
    raw = content if isinstance(content, str) else json.dumps(content)
    config_path.write_text(raw, encoding='utf-8')
    return config_path


class TestCliGeneral:
    """Test general CLI invocation, help output, argument validation, and entrypoint."""

    @pytest.mark.parametrize('flag', ['--help', '-h'])
    def test_help_option_displays_usage(self, cli_runner: CliRunner, flag: str) -> None:
        """Verify --help and -h exit cleanly and display CLI options."""
        result = cli_runner.invoke(main, [flag])
        assert result.exit_code == 0
        assert 'cpuz_parser' in result.output.lower()
        assert '--format' in result.output
        assert '--auto-combine-slots' in result.output

    def test_missing_report_argument_fails_with_usage_error(self, cli_runner: CliRunner) -> None:
        """Verify invoking the CLI without REPORT_FILE exits with code 2."""
        result = cli_runner.invoke(main, [])
        assert result.exit_code == 2
        assert "Missing argument 'REPORT_FILE'" in result.output

    def test_nonexistent_report_file_fails_with_bad_parameter(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Verify passing a missing report path exits with code 2 and a clear error."""
        missing_path = tmp_path / 'nonexistent_report.txt'
        result = cli_runner.invoke(main, [str(missing_path)])
        assert result.exit_code == 2
        assert missing_path.name in result.output
        assert 'does not exist' in result.output

    def test_module_entrypoint_invokes_main_only_when_run_as_script(self) -> None:
        """Verify python -m cpuz_parser calls main() only under __main__."""
        with patch('cpuz_parser.cli.main', return_value=0) as mock_main:
            runpy.run_module('cpuz_parser.__main__', run_name='__main__')
            mock_main.assert_called_once_with()

        with patch('cpuz_parser.cli.main') as mock_main:
            runpy.run_module('cpuz_parser.__main__', run_name='cpuz_parser.__main__')
            mock_main.assert_not_called()


class TestCliConfig:
    """Test JSON configuration loading, validation, and CLI application."""

    def test_load_config_parses_valid_options(self, tmp_path: Path) -> None:
        """Verify load_config parses both supported options into a CliConfig instance."""
        config_path = _write_config(
            tmp_path,
            {
                'auto_combine_slots': False,
                'ram_freqs_single_mul2_to_friendly': {'2132': '2133'},
            },
        )
        assert load_config(config_path) == CliConfig(
            ram_freqs_single_mul2_to_friendly={'2132': '2133'},
            auto_combine_slots=False,
        )

    def test_load_config_empty_object_returns_defaults(self, tmp_path: Path) -> None:
        """Verify an empty JSON object loads as a CliConfig with all fields unset."""
        config_path = _write_config(tmp_path, '{}', filename='empty.json')
        assert load_config(config_path) == CliConfig()

    def test_load_example_config_file(self) -> None:
        """Verify the shipped config.example.json conforms to the CliConfig schema."""
        example_path = Path(__file__).resolve().parent.parent / 'config.example.json'
        loaded = load_config(example_path)
        assert isinstance(loaded.auto_combine_slots, bool)
        assert loaded.ram_freqs_single_mul2_to_friendly

    def test_cli_applies_ram_freq_translate_from_config(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        """Verify -c/--config applies ram_freqs_single_mul2_to_friendly to parsed RAM slots."""
        config_path = _write_config(
            tmp_path,
            {'ram_freqs_single_mul2_to_friendly': {'2666': '2667'}},
        )
        result = cli_runner.invoke(
            main,
            [str(sample_report_path), '-c', str(config_path), '-f', 'plain', '-o', '-'],
        )
        assert result.exit_code == 0
        assert '2x DDR4 2667MHz 8GB DUMMY_MEM_CORP' in result.output

    @pytest.mark.parametrize(
        ('raw_content', 'expected_error'),
        [
            pytest.param('{invalid json', 'Malformed JSON in config file', id='malformed_json'),
            pytest.param('[1, 2, 3]', 'must contain a JSON object', id='non_object_root'),
            pytest.param(
                json.dumps({'ram_freqs_single_mul2_to_friendly': ['not', 'a', 'dict']}),
                "Config key 'ram_freqs_single_mul2_to_friendly'",
                id='ram_freqs_not_dict',
            ),
            pytest.param(
                json.dumps({'ram_freqs_single_mul2_to_friendly': {'2132': 2133}}),
                "Config key 'ram_freqs_single_mul2_to_friendly'",
                id='ram_freqs_non_str_value',
            ),
            pytest.param(
                json.dumps({'auto_combine_slots': 'false'}),
                "Config key 'auto_combine_slots' must be a boolean",
                id='auto_combine_str_value',
            ),
            pytest.param(
                json.dumps({'auto_combine_slots': 0}),
                "Config key 'auto_combine_slots' must be a boolean",
                id='auto_combine_int_value',
            ),
            pytest.param(
                json.dumps({'auto_combine_slots': None}),
                "Config key 'auto_combine_slots' must be a boolean",
                id='auto_combine_null_value',
            ),
        ],
    )
    def test_malformed_config_exits_with_code_1(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        raw_content: str,
        expected_error: str,
    ) -> None:
        """Verify malformed or invalid config files abort with exit code 1 and an error message."""
        config_path = _write_config(tmp_path, raw_content, filename='bad_config.json')
        result = cli_runner.invoke(main, [str(sample_report_path), '-c', str(config_path), '-f', 'json', '-o', '-'])
        assert result.exit_code == 1
        assert expected_error in result.output


class TestCliAutoCombineSlots:
    """Test --auto-combine-slots/--no-auto-combine-slots flags and config precedence."""

    @pytest.mark.parametrize(
        ('cli_flags', 'config_data', 'expect_combined'),
        [
            pytest.param([], None, True, id='default_true'),
            pytest.param(['--no-auto-combine-slots'], None, False, id='cli_false_no_config'),
            pytest.param(['--auto-combine-slots'], None, True, id='cli_true_no_config'),
            pytest.param([], {'auto_combine_slots': False}, False, id='config_false_no_cli'),
            pytest.param([], {'auto_combine_slots': True}, True, id='config_true_no_cli'),
            pytest.param(
                [],
                {'ram_freqs_single_mul2_to_friendly': {}},
                True,
                id='config_missing_key_default_true',
            ),
            pytest.param(
                ['--auto-combine-slots'],
                {'auto_combine_slots': False},
                True,
                id='cli_true_overrides_config_false',
            ),
            pytest.param(
                ['--no-auto-combine-slots'],
                {'auto_combine_slots': True},
                False,
                id='cli_false_overrides_config_true',
            ),
        ],
    )
    def test_precedence_between_cli_flags_and_config(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        expected_sample_system_info: dict[str, Any],
        expected_uncombined_sample_slots: list[dict[str, str]],
        cli_flags: list[str],
        config_data: dict[str, Any] | None,
        expect_combined: bool,
    ) -> None:
        """Verify CLI flags override config file settings, which in turn override the True default."""
        out_file = tmp_path / 'out.json'
        args = [str(sample_report_path), *cli_flags, '-o', str(out_file)]
        if config_data is not None:
            config_path = _write_config(tmp_path, config_data)
            args.extend(['-c', str(config_path)])

        result = cli_runner.invoke(main, args)
        assert result.exit_code == 0
        data = json.loads(out_file.read_text(encoding='utf-8'))
        expected_slots = (
            expected_sample_system_info['ram']['slots'] if expect_combined else expected_uncombined_sample_slots
        )
        assert data['ram']['slots'] == expected_slots

    def test_stdin_respects_no_auto_combine_slots(
        self,
        cli_runner: CliRunner,
        sample_report_content: str,
        tmp_path: Path,
        expected_uncombined_sample_slots: list[dict[str, str]],
    ) -> None:
        """Verify reading from stdin forwards --no-auto-combine-slots to the parser."""
        out_file = tmp_path / 'stdin_out.json'
        result = cli_runner.invoke(
            main,
            ['-', '--no-auto-combine-slots', '-o', str(out_file)],
            input=sample_report_content.encode('cp1252'),
        )
        assert result.exit_code == 0
        data = json.loads(out_file.read_text(encoding='utf-8'))
        assert data['ram']['slots'] == expected_uncombined_sample_slots


class TestCliInputAndOutput:
    """Test stdin/file input, stdout/file output, extension deduction, and explicit formats."""

    def test_reads_report_from_stdin(
        self,
        cli_runner: CliRunner,
        sample_report_content: str,
    ) -> None:
        """Verify passing '-' as REPORT_FILE parses cp1252 report bytes from stdin."""
        result = cli_runner.invoke(
            main,
            ['-', '-f', 'plain', '-o', '-'],
            input=sample_report_content.encode('cp1252'),
        )
        assert result.exit_code == 0
        assert 'Motherboard: DUMMY Vendor Corp DUMMY Mainboard Model' in result.output
        assert 'CPU: DUMMY Processor Model 8-Core' in result.output

    @pytest.mark.parametrize(
        'output_args',
        [
            pytest.param([], id='omitted_output_option'),
            pytest.param(['-o', '-'], id='explicit_stdout_dash'),
        ],
    )
    def test_writes_plain_output_to_stdout(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        output_args: list[str],
    ) -> None:
        """Verify plain format prints parsed hardware data to stdout by default and with -o -."""
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'plain', *output_args])
        assert result.exit_code == 0
        assert 'Motherboard: DUMMY Vendor Corp DUMMY Mainboard Model' in result.output
        assert '2x DDR4 2666MHz 8GB DUMMY_MEM_CORP' in result.output

    @pytest.mark.parametrize(
        ('filename', 'expected_markers'),
        [
            pytest.param('report.json', ('"motherboard"', 'DUMMY Vendor Corp'), id='json'),
            pytest.param('report.xml', ('<system_info>', 'DUMMY Vendor Corp'), id='xml'),
            pytest.param('report.txt', ('Motherboard: DUMMY Vendor Corp',), id='txt_plain'),
            pytest.param('report.custom', ('Motherboard: DUMMY Vendor Corp',), id='unknown_ext_plain_fallback'),
            pytest.param(
                'report.yaml',
                ('motherboard:', 'DUMMY Vendor Corp'),
                marks=pytest.mark.skipif(not FEATURE_YAML, reason='pyyaml is not installed'),
                id='yaml',
            ),
            pytest.param(
                'report.yml',
                ('motherboard:', 'DUMMY Vendor Corp'),
                marks=pytest.mark.skipif(not FEATURE_YAML, reason='pyyaml is not installed'),
                id='yml',
            ),
            pytest.param(
                'report.toml',
                ('[motherboard]', 'DUMMY Vendor Corp'),
                marks=pytest.mark.skipif(not FEATURE_TOML, reason='tomli-w is not installed'),
                id='toml',
            ),
        ],
    )
    def test_deduces_format_from_output_extension(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        filename: str,
        expected_markers: tuple[str, ...],
    ) -> None:
        """Verify output file extensions select the matching exporter or fall back to plain text."""
        out_file = tmp_path / filename
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        content = out_file.read_text(encoding='utf-8')
        for marker in expected_markers:
            assert marker in content, f'Missing expected marker {marker!r} in {filename}'

    def test_explicit_format_overrides_output_extension(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify an explicit case-insensitive -f/--format overrides file extension deduction."""
        out_file = tmp_path / 'report.txt'
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'JSON', '-o', str(out_file)])
        assert result.exit_code == 0
        assert json.loads(out_file.read_text(encoding='utf-8')) == expected_sample_system_info

    def test_export_rich_to_stdout_uses_rich_exporter(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify -f rich with stdout delegates rendering to exporters.to_rich."""
        with patch('cpuz_parser.exporters.to_rich', autospec=True) as mock_to_rich:
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'rich', '-o', '-'])
            assert result.exit_code == 0
            mock_to_rich.assert_called_once()
            passed_parser = mock_to_rich.call_args.args[0]
            assert passed_parser.system_info == expected_sample_system_info

    def test_export_rich_to_file_renders_rich_layout_without_ansi(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        """Verify -f rich targeting a file writes Rich panels/tables without ANSI control codes."""
        out_file = tmp_path / 'report.rich.txt'
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'rich', '-o', str(out_file)])
        assert result.exit_code == 0
        content = out_file.read_text(encoding='utf-8')
        assert '\x1b' not in content
        assert 'Motherboard' in content
        assert 'Installed RAM Slots' in content
        assert 'DUMMY Vendor Corp' in content
        assert '2x DDR4 2666MHz 8GB DUMMY_MEM_CORP' in content

    def test_export_json_to_stdout_with_rich_uses_console_print_json(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        expected_sample_system_info: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify JSON stdout output uses Rich Console.print_json when Rich is enabled."""
        monkeypatch.setattr(cpuz_parser.cli, 'FEATURE_RICH', True)
        with patch('rich.console.Console.print_json', autospec=True) as mock_print_json:
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'json', '-o', '-'])
            assert result.exit_code == 0
            mock_print_json.assert_called_once()
            rendered_json = mock_print_json.call_args.args[1]
            assert json.loads(rendered_json) == expected_sample_system_info

    def test_export_json_to_stdout_without_rich_echoes_json(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        expected_sample_system_info: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify JSON stdout output echoes valid JSON directly when Rich is disabled."""
        monkeypatch.setattr(cpuz_parser.cli, 'FEATURE_RICH', False)
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'json', '-o', '-'])
        assert result.exit_code == 0
        assert json.loads(result.output) == expected_sample_system_info


class TestCliFallbacksAndErrors:
    """Test non-Rich fallbacks and CLI error handling."""

    def test_stdout_defaults_to_plain_when_rich_disabled(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify omitting -f defaults stdout output to plain text when Rich is unavailable."""
        monkeypatch.setattr(cpuz_parser.cli, 'FEATURE_RICH', False)
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', '-'])
        assert result.exit_code == 0
        assert 'Motherboard: DUMMY Vendor Corp DUMMY Mainboard Model' in result.output

    def test_file_export_echoes_plain_success_message_when_rich_disabled(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify file export prints a plain confirmation message when Rich is disabled."""
        out_file = tmp_path / 'report.txt'
        monkeypatch.setattr(cpuz_parser.cli, 'FEATURE_RICH', False)
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        assert f'Report successfully exported to: {out_file}' in result.output

    @pytest.mark.parametrize(
        ('format_name', 'feature_flag', 'output_target', 'expected_error'),
        [
            pytest.param(
                'rich',
                'FEATURE_RICH',
                'rich.txt',
                "Rich visualization requires 'rich' and 'rich-click'",
                id='missing_rich_to_file',
            ),
            pytest.param(
                'yaml',
                'FEATURE_YAML',
                '-',
                "YAML export feature is disabled because 'pyyaml' is not installed",
                id='missing_yaml',
            ),
            pytest.param(
                'toml',
                'FEATURE_TOML',
                '-',
                "TOML export feature is disabled because 'tomli-w' is not installed",
                id='missing_toml',
            ),
        ],
    )
    def test_missing_optional_dependency_fails_with_usage_error(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        format_name: str,
        feature_flag: str,
        output_target: str,
        expected_error: str,
    ) -> None:
        """Verify missing optional exporter dependencies exit with code 2 and installation hints."""
        monkeypatch.setattr(f'cpuz_parser.features.{feature_flag}', False)
        out_arg = output_target if output_target == '-' else str(tmp_path / output_target)
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', format_name, '-o', out_arg])
        assert result.exit_code == 2
        assert expected_error in result.output

    def test_unsupported_format_in_callback_raises_usage_error(
        self,
        sample_report_path: Path,
    ) -> None:
        """Verify calling main.callback with an unsupported format raises click.UsageError."""
        assert main.callback is not None
        with pytest.raises(click.UsageError, match="Unsupported format: 'invalid_format'"):
            main.callback(
                report_file=str(sample_report_path),
                config_file=None,
                auto_combine_slots=None,
                output_format='invalid_format',
                output_file='-',
            )

    def test_import_falls_back_to_standard_click_when_rich_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify importing cpuz_parser.cli falls back to standard click without polluting module state."""
        original_cli_module = cpuz_parser.cli
        monkeypatch.setattr('cpuz_parser.features.FEATURE_RICH', False)
        monkeypatch.setitem(sys.modules, 'rich_click', None)
        monkeypatch.delitem(sys.modules, 'cpuz_parser.cli')
        monkeypatch.setattr(cpuz_parser, 'cli', original_cli_module)

        fallback_cli = importlib.import_module('cpuz_parser.cli')

        assert fallback_cli is not original_cli_module
        assert fallback_cli.click.__name__ == 'click'

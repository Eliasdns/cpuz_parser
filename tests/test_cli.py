"""Automated tests for cpuz_parser CLI options and feature toggles."""

from __future__ import annotations

import importlib
import json
import runpy
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

import cpuz_parser.cli
from cpuz_parser.cli import main
from cpuz_parser.features import FEATURE_TOML, FEATURE_YAML


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.unit


class TestCliGeneral:
    """Test general CLI usage, help display, and parameter validation."""

    def test_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'cpuz' in result.output.lower()
        assert '--format' in result.output

    def test_help_short_option(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, ['-h'])
        assert result.exit_code == 0
        assert 'cpuz' in result.output.lower()
        assert '--format' in result.output

    def test_missing_report_argument(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Missing argument 'REPORT_FILE'" in result.output

    def test_nonexistent_report_file(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, ['nonexistent_report.txt'])
        assert result.exit_code != 0
        assert "File 'nonexistent_report.txt'" in result.output

    def test_main_entrypoint(self) -> None:
        with patch.object(sys, 'argv', ['cpuz_parser', '--help']), patch('cpuz_parser.cli.main', return_value=0) as mock_main:
            runpy.run_module('cpuz_parser.__main__', run_name='__main__')
            mock_main.assert_called_once()

        with patch('cpuz_parser.cli.main') as mock_main:
            runpy.run_module('cpuz_parser.__main__', run_name='cpuz_parser.__main__')
            mock_main.assert_not_called()


class TestCliConfig:
    """Test RAM frequency configuration file loading."""

    def test_config_file_loading(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / 'config.json'
        config_data = {
            'ram_freqs_single_mul2_to_friendly': {
                '2666': '2666-TRANSLATED',
            }
        }
        config_path.write_text(json.dumps(config_data), encoding='utf-8')

        result = cli_runner.invoke(
            main,
            [str(sample_report_path), '-c', str(config_path), '-f', 'plain', '-o', '-'],
        )
        assert result.exit_code == 0
        assert '2666-TRANSLATED' in result.output


class TestCliInputOutput:
    """Test stdin reading and stdout/file output writing."""

    def test_stdin_reading(
        self,
        cli_runner: CliRunner,
        sample_report_content: str,
    ) -> None:
        content_bytes = sample_report_content.encode('cp1252')
        result = cli_runner.invoke(main, ['-', '-f', 'plain', '-o', '-'], input=content_bytes)
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output

    def test_stdout_default(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'plain'])
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output


class TestCliExportFormats:
    """Test built-in and optional structured export formats."""

    def test_export_plain_to_stdout(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'plain', '-o', '-'])
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output

    def test_export_rich_to_stdout(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        with patch('cpuz_parser.exporters.to_rich') as mock_to_rich:
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'rich', '-o', '-'])
            assert result.exit_code == 0
            mock_to_rich.assert_called_once()

    def test_export_rich_to_file(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.rich.txt'
        result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'rich', '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert 'Motherboard:' in out_file.read_text(encoding='utf-8')

    def test_export_json_stdout_rich(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        with patch('cpuz_parser.cli.FEATURE_RICH', True), patch('rich.console.Console.print_json') as mock_print_json:
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'json', '-o', '-'])
            assert result.exit_code == 0
            mock_print_json.assert_called_once()

    def test_export_json_stdout_non_rich(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        with patch('cpuz_parser.cli.FEATURE_RICH', False):
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'json', '-o', '-'])
            assert result.exit_code == 0
            assert '"motherboard"' in result.output

    def test_export_json(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.json'
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert '"motherboard"' in out_file.read_text(encoding='utf-8')

    def test_export_xml(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.xml'
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert '<system_info>' in out_file.read_text(encoding='utf-8')

    def test_export_yaml(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.yaml'
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        if FEATURE_YAML:
            assert result.exit_code == 0
            assert out_file.exists()
            assert 'motherboard:' in out_file.read_text(encoding='utf-8')
        else:
            assert result.exit_code != 0
            assert "requires 'pyyaml'" in result.output

    def test_export_toml(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.toml'
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        if FEATURE_TOML:
            assert result.exit_code == 0
            assert out_file.exists()
            assert '[motherboard]' in out_file.read_text(encoding='utf-8')
        else:
            assert result.exit_code != 0
            assert "requires 'tomli-w'" in result.output


class TestCliDeductionAndFallbacks:
    """Test format deduction, unknown formats, and non-Rich fallbacks."""

    @pytest.mark.parametrize(
        ('filename', 'expected_content_sub'),
        [
            ('out.json', '"motherboard"'),
            ('out.xml', '<system_info>'),
            ('out.txt', 'Motherboard:'),
            ('out.custom', 'Motherboard:'),
        ],
    )
    def test_format_deduction_and_unknown_fallback(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
        filename: str,
        expected_content_sub: str,
    ) -> None:
        out_file = tmp_path / filename
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert expected_content_sub in out_file.read_text(encoding='utf-8')

    def test_format_deduction_yaml_yml(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        if not FEATURE_YAML:
            pytest.skip("YAML dependency not installed")
        out_file = tmp_path / 'out.yml'
        result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
        assert result.exit_code == 0
        assert 'motherboard:' in out_file.read_text(encoding='utf-8')

    def test_stdout_format_deduction_when_feature_rich_false(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        with patch('cpuz_parser.cli.FEATURE_RICH', False):
            result = cli_runner.invoke(main, [str(sample_report_path), '-o', '-'])
            assert result.exit_code == 0
            assert 'Motherboard:' in result.output

    def test_file_export_success_message_non_rich(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / 'report.txt'
        with patch('cpuz_parser.cli.FEATURE_RICH', False):
            result = cli_runner.invoke(main, [str(sample_report_path), '-o', str(out_file)])
            assert result.exit_code == 0
            assert f'Report successfully exported to: {out_file}' in result.output

    def test_exporter_import_error_raises_usage_error(
        self,
        cli_runner: CliRunner,
        sample_report_path: Path,
    ) -> None:
        with patch('cpuz_parser.exporters.to_plain', side_effect=ImportError('Simulated missing dependency')):
            result = cli_runner.invoke(main, [str(sample_report_path), '-f', 'plain', '-o', '-'])
            assert result.exit_code != 0
            assert 'Simulated missing dependency' in result.output

    def test_unsupported_format_raises_usage_error(
        self,
        sample_report_path: Path,
    ) -> None:
        # Pass an unsupported format directly to main.callback to trigger match default
        assert main.callback is not None
        with pytest.raises(Exception) as exc_info:
            main.callback(
                report_file=str(sample_report_path),
                config_file=None,
                output_format='invalid_format',
                output_file='-',
            )
        assert "Unsupported format: 'invalid_format'" in str(exc_info.value)

    def test_cli_import_time_fallback_when_rich_false(self) -> None:
        with patch('cpuz_parser.features.FEATURE_RICH', False), patch.dict('sys.modules', {'rich_click': None}):
            reloaded = importlib.reload(cpuz_parser.cli)
            assert reloaded.click is not None
        # Restore module state
        importlib.reload(cpuz_parser.cli)

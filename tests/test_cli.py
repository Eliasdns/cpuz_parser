"""Automated tests for cpuz_parser CLI options and feature toggles."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cpuz_parser.cli import main
from cpuz_parser.features import FEATURE_TOML, FEATURE_YAML


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.unit

FIXTURES_DIR = (Path(__file__).parent / '../fixtures').resolve()
ALL_TXT_REPORTS_DIR = FIXTURES_DIR / 'cpuz-reports/TXTs'
# TODO: log/info for the selected 'SAMPLE_REPORT'
SAMPLE_REPORT = next(ALL_TXT_REPORTS_DIR.glob('*.txt'))

if SAMPLE_REPORT is None or not SAMPLE_REPORT.exists():
    raise FileNotFoundError(
        f"No CPU-Z test report (.txt) was found in: '{ALL_TXT_REPORTS_DIR}'"
    )


class TestCliGeneral:
    """Test general CLI usage, help display, and parameter validation."""

    def test_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'cpuz_parser' in result.output
        assert '--format' in result.output

    def test_missing_report_argument(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Missing argument 'REPORT_FILE'" in result.output

    def test_nonexistent_report_file(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, ['nonexistent_report.txt'])
        assert result.exit_code != 0
        assert "File 'nonexistent_report.txt'" in result.output


class TestCliInputOutput:
    """Test stdin reading and stdout/file output writing."""

    def test_stdin_reading(self, cli_runner: CliRunner) -> None:
        content = SAMPLE_REPORT.read_bytes()
        result = cli_runner.invoke(main, ['-', '-f', 'plain', '-o', '-'], input=content)
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output

    def test_stdout_default(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-f', 'plain'])
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output


class TestCliExportFormats:
    """Test built-in and optional structured export formats."""

    def test_export_plain(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-f', 'plain', '-o', '-'])
        assert result.exit_code == 0
        assert 'Motherboard:' in result.output

    def test_export_json(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        out_file = tmp_path / 'report.json'
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert '"motherboard"' in out_file.read_text(encoding='utf-8')

    def test_export_xml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        out_file = tmp_path / 'report.xml'
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-o', str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert '<system_info>' in out_file.read_text(encoding='utf-8')

    def test_export_yaml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        out_file = tmp_path / 'report.yaml'
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-o', str(out_file)])
        if FEATURE_YAML:
            assert result.exit_code == 0
            assert out_file.exists()
            assert 'motherboard:' in out_file.read_text(encoding='utf-8')
        else:
            assert result.exit_code != 0
            assert "requires 'pyyaml'" in result.output

    def test_export_toml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        out_file = tmp_path / 'report.toml'
        result = cli_runner.invoke(main, [str(SAMPLE_REPORT), '-o', str(out_file)])
        if FEATURE_TOML:
            assert result.exit_code == 0
            assert out_file.exists()
            assert '[motherboard]' in out_file.read_text(encoding='utf-8')
        else:
            assert result.exit_code != 0
            assert "requires 'tomli-w'" in result.output

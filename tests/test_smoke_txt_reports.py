"""Parameterized smoke tests verifying real CPU-Z TXT reports parse cleanly."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cpuz_parser.cli import main
from cpuz_parser.parsers import CpuzTxtParser


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.smoke


PRIV_FIXTURES_DIR = (Path(__file__).parent / '../priv_fixtures').resolve()
ALL_TXT_REPORTS_DIR = PRIV_FIXTURES_DIR / 'real-cpuz-reports/TXTs'
REPORT_TXT_FILES = sorted(ALL_TXT_REPORTS_DIR.glob('*.txt'))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parameterize test cases with all discovered real CPU-Z TXT reports."""
    if 'report_file' in metafunc.fixturenames:
        if not ALL_TXT_REPORTS_DIR.exists() or not REPORT_TXT_FILES:
            metafunc.parametrize('report_file', [None], ids=['missing_fixtures'])
        else:
            metafunc.parametrize('report_file', REPORT_TXT_FILES, ids=[f.name for f in REPORT_TXT_FILES])


class TestTxtReports:
    """Smoke tests validating all real CPU-Z TXT fixture reports."""

    @pytest.fixture(autouse=True)
    def validate_fixtures_exist(self, report_file: Path | None) -> None:
        """Ensure real report fixtures exist. And fail explicitly if missing."""
        if report_file is None:
            pytest.fail(
                f"No real CPU-Z report (.txt) was found in '{ALL_TXT_REPORTS_DIR}'. "
                'These fixtures are required to run the Smoke Tests.'
            )

    def test_parse_report_extracts_hardware_info(self, report_file: Path) -> None:
        """Verify CpuzTxtParser parses without error and populates all core hardware sections."""
        parser = CpuzTxtParser(str(report_file))
        info = parser.system_info

        assert info['motherboard']['vendor'] and info['motherboard']['model'], (
            f'Motherboard vendor or model is empty in {report_file.name}'
        )
        assert info['bios']['vendor'] and info['bios']['version'] and info['bios']['date'], (
            f'BIOS vendor, version or date is empty in {report_file.name}'
        )
        assert info['cpu'] and all(info['cpu']), (
            f'Missing or blank CPU entry in {report_file.name}'
        )
        assert info['ram']['size'], (
            f'RAM size is empty in {report_file.name}'
        )
        assert info['ram']['slots'] and all(info['ram']['slots']), (
            f'Missing or blank RAM slot entry in {report_file.name}'
        )
        assert info['gpu'] and all(info['gpu']), (
            f'Missing or blank GPU entry in {report_file.name}'
        )
        assert info['os'] and all(info['os']), (
            f'Missing or blank OS entry in {report_file.name}'
        )

        info_str = str(parser)
        assert info['cpu'][0] in info_str, f'CPU not found in str(parser) for {report_file.name}'
        assert info['ram']['size'] in info_str, f'RAM size not found in str(parser) for {report_file.name}'

    def test_cli_renders_to_plain(self, report_file: Path, cli_runner: CliRunner) -> None:
        """Verify CLI execution handles the report file and outputs all plain-text sections."""
        result = cli_runner.invoke(main, [str(report_file), '-f', 'plain', '-o', '-'])
        assert result.exit_code == 0, f'CLI failed with exit code {result.exit_code}: {result.output}'
        assert result.exception is None

        expected_sections = (
            'Motherboard:',
            'BIOS:',
            'CPU:',
            'Memory:', 'DDR',
            'Graphics:',
            'Operating System:',
        )
        for section in expected_sections:
            assert section in result.output, f"Missing '{section}' in CLI output for {report_file.name}"

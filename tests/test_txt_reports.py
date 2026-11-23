"""Parameterized tests verifying that all CPU-Z TXT fixture reports parse without error."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cpuz_parser import CpuzTxtParser
from cpuz_parser.cli import main


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.smoke


FIXTURES_DIR = (Path(__file__).parent / '../fixtures').resolve()
ALL_TXT_REPORTS_DIR = FIXTURES_DIR / 'real-cpuz-reports/TXTs'
REPORT_TXT_FILES = sorted(ALL_TXT_REPORTS_DIR.glob('*.txt'))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parameterize test cases with all discovered CPU-Z TXT reports."""
    if 'report_file' in metafunc.fixturenames:
        metafunc.parametrize('report_file', REPORT_TXT_FILES, ids=[f.name for f in REPORT_TXT_FILES])


class TestTxtReports:
    def test_parse_report_no_exception(self, report_file: Path) -> None:
        """Verify CpuzTxtParser instantiates and parses without raising any exception."""
        parser = CpuzTxtParser(str(report_file))

        info = parser.system_info
        assert isinstance(info, dict)
        for expected_key in ('motherboard', 'bios', 'cpu', 'ram', 'gpu', 'os'):
            assert expected_key in info, f"Missing key '{expected_key}' in {report_file.name}"

        info_str = str(parser)
        assert isinstance(info_str, str)
        assert len(info_str) > 0


    def test_report_data_populated(self, report_file: Path) -> None:
        """Verify parsed data contains populated essential hardware values."""
        parser = CpuzTxtParser(str(report_file))
        info = parser.system_info

        assert len(info['cpu']) > 0, f'No CPU entries found in {report_file.name}'
        assert info['ram']['size'], f'RAM size is empty in {report_file.name}'

        has_mb = bool(info['motherboard']['vendor'] or info['motherboard']['model'])
        has_bios = bool(info['bios']['vendor'] or info['bios']['version'])
        assert has_mb or has_bios, f'Neither motherboard nor BIOS info found in {report_file.name}'


    def test_cli_execution_no_exception(self, report_file: Path, cli_runner: CliRunner) -> None:
        """Verify CLI execution handles the report file without exceptions."""
        result = cli_runner.invoke(main, [str(report_file), '-f', 'plain', '-o', '-'])
        assert result.exit_code == 0

        assert 'Motherboard:' in result.output
        assert 'CPU:' in result.output
        assert 'Memory:' in result.output

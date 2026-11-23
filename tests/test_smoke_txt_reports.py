"""Parameterized tests verifying that all real CPU-Z TXT reports parse without error."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cpuz_parser.cli import main
from cpuz_parser.parsers import CpuzTxtParser


if TYPE_CHECKING:
    from click.testing import CliRunner


pytestmark = pytest.mark.smoke


PRIV_FIXTURES_DIR = (Path(__file__).parent / '../private-fixtures').resolve()
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
        """Ensure real report fixtures exist; fail explicitly if missing."""
        if report_file is None:
            pytest.fail(
                f"No real CPU-Z report (.txt) was found in '{ALL_TXT_REPORTS_DIR}'. "
                'These fixtures are required to run the Smoke Tests.'
            )

    def test_parse_report_no_exception(self, report_file: Path) -> None:
        """Verify CpuzTxtParser instantiates, parses without exception, and extracts core hardware data."""
        parser = CpuzTxtParser(str(report_file))
        info = parser.system_info

        # Verify all essential hardware categories are extracted and populated
        assert \
            info['motherboard']['vendor'] and info['motherboard']['model'],\
            f'Motherboard vendor or model are empty in {report_file.name}'
        assert \
            info['bios']['vendor'] and info['bios']['version'] and info['bios']['date'],\
            f'BIOS vendor, version or date are empty in {report_file.name}'
        assert \
            len(info['cpu']),\
            f'No CPU entries parsed in {report_file.name}'
        assert \
            all(info['cpu']),\
            f'Are a blank string parsed as a CPU entry in {report_file.name}'
        assert \
            info['ram']['size'],\
            f'RAM size is empty in {report_file.name}'
        assert \
            len(info['ram']['slots']),\
            f'No RAM slots parsed in {report_file.name}'
        assert \
            all(info['ram']['slots']),\
            f'Are a blank string parsed as a RAM slot in {report_file.name}'
        assert \
            len(info['gpu']),\
            f'No GPU entries parsed in {report_file.name}'
        assert \
            all(info['gpu']),\
            f'Are a blank string parsed as a GPU in {report_file.name}'
        assert \
            len(info['os']) and all(info['gpu']),\
            f'No OS entries parsed in {report_file.name}'

        # Verify plain-text rendering anchors to actual parsed hardware data
        info_str = str(parser)
        assert info['cpu'][0] in info_str, f'CPU not found in str(parser) for {report_file.name}'
        assert info['ram']['size'] in info_str, f'RAM size not found in str(parser) for {report_file.name}'

    def test_cli_execution_no_exception(self, report_file: Path, cli_runner: CliRunner) -> None:
        """Verify CLI execution handles the report file without exceptions."""
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

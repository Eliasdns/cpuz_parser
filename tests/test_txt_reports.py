"""Parameterized tests verifying that all CPU-Z TXT fixture reports parse without error."""

from __future__ import annotations

from pathlib import Path

import pytest

from cpuz_parser import CpuzTxtParser
from cpuz_parser.cpuz_parser import system_info_cli


pytestmark = pytest.mark.smoke


FIXTURES_DIR = (Path(__file__).parent / '../fixtures').resolve()
REPORTS_TXT_DIR = FIXTURES_DIR / 'cpuz-reports/TXTs'
REPORTS_TXT_FILES = sorted(REPORTS_TXT_DIR.glob('*.txt'))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parameterize test cases with all discovered CPU-Z TXT reports."""
    if 'report_file' in metafunc.fixturenames:
        metafunc.parametrize('report_file', REPORTS_TXT_FILES, ids=[f.name for f in REPORTS_TXT_FILES])


def test_parse_report_no_exception(report_file: Path) -> None:
    """Verify CpuzTxtParser instantiates and parses without raising any exception."""
    parser = CpuzTxtParser(str(report_file))

    info = parser.system_info
    assert isinstance(info, dict)
    for expected_key in ('motherboard', 'bios', 'cpu', 'ram', 'gpu', 'os'):
        assert expected_key in info, f"Missing key '{expected_key}' in {report_file.name}"

    info_str = parser.system_info_str
    assert isinstance(info_str, str)
    assert len(info_str) > 0


def test_report_data_populated(report_file: Path) -> None:
    """Verify parsed data contains populated essential hardware values."""
    parser = CpuzTxtParser(str(report_file))
    info = parser.system_info

    assert len(info['cpu']) > 0, f'No CPU entries found in {report_file.name}'
    assert info['ram']['size'], f'RAM size is empty in {report_file.name}'

    has_mb = bool(info['motherboard']['vendor'] or info['motherboard']['model'])
    has_bios = bool(info['bios']['vendor'] or info['bios']['version'])
    assert has_mb or has_bios, f'Neither motherboard nor BIOS info found in {report_file.name}'


def test_cli_execution_no_exception(report_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify CLI execution handles the report file without exceptions."""
    system_info_cli(argv=['cpuz-parser', str(report_file), 'nopause'])
    captured = capsys.readouterr()

    assert 'Motherboard:' in captured.out
    assert 'CPU:' in captured.out
    assert 'Memory:' in captured.out

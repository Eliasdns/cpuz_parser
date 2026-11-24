"""Shared pytest fixtures for the cpuz_parser test suite."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from cpuz_parser.parsers import CpuzTxtParser


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Click's CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to unit test synthetic fixtures directory."""
    return Path(__file__).parent / 'fixtures'


@pytest.fixture
def sample_report_path(fixtures_dir: Path) -> Path:
    """Path to the synthetic CPU-Z sample report file."""
    return fixtures_dir / 'sample_report.txt'


@pytest.fixture
def sample_report_content(sample_report_path: Path) -> str:
    """Contents of the synthetic CPU-Z sample report file."""
    return sample_report_path.read_text(encoding='cp1252')


@pytest.fixture
def section_contents(fixtures_dir: Path) -> dict[str, str]:
    """Dictionary mapping section names to their isolated text content."""
    sections_dir = fixtures_dir / 'sections'
    return {
        file.stem: file.read_text(encoding='cp1252')
        for file in sections_dir.glob('*.txt')
    }


@pytest.fixture
def sample_parser(sample_report_path: Path) -> CpuzTxtParser:
    """Initialized CpuzTxtParser parsed from the synthetic sample report."""
    return CpuzTxtParser(str(sample_report_path))


@pytest.fixture
def empty_system_info() -> dict[str, Any]:
    """Fresh default empty structure expected from an unpopulated SystemInfo."""
    return {
        'motherboard': {'vendor': '', 'model': ''},
        'bios': {'vendor': '', 'version': '', 'date': ''},
        'cpu': [],
        'ram': {'size': '', 'slots': []},
        'gpu': [],
        'os': [],
    }


@pytest.fixture
def expected_sample_system_info() -> dict[str, Any]:
    """Fresh expected system_info dictionary parsed from sample_report.txt."""
    return {
        'motherboard': {'vendor': 'DUMMY Vendor Corp', 'model': 'DUMMY Mainboard Model'},
        'bios': {'vendor': 'DUMMY_BIOS_CORP', 'version': 'V1.0.0', 'date': '01/01/2025'},
        'cpu': ['DUMMY Processor Model 8-Core'],
        'ram': {
            'size': '16GB',
            'slots': ['2x DDR4 2666MHz 8GB DUMMY_MEM_CORP'],
        },
        'gpu': ['DUMMY Graphics Adapter'],
        'os': ['DUMMY Operating System 64-bit'],
    }


@pytest.fixture
def expected_uncombined_sample_slots() -> list[dict[str, str]]:
    """Fresh uncombined RAM slot dictionaries expected from sample_report.txt."""
    slot = {'type': 'DDR4', 'bandwidth': '2666MHz', 'size': '8GB', 'manufacturer': 'DUMMY_MEM_CORP'}
    return [slot.copy(), slot.copy()]

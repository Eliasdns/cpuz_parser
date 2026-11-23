from pathlib import Path

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

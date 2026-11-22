import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Click's CliRunner for testing CLI commands."""
    return CliRunner()

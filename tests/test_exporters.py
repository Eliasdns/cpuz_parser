"""Unit tests for cpuz_parser data serializers and formatters."""

from __future__ import annotations

import json
import tomllib
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from cpuz_parser import exporters
from cpuz_parser.features import FEATURE_RICH, FEATURE_TOML, FEATURE_YAML
from cpuz_parser.parsers import CpuzTxtParser, SystemInfo


if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.unit


@pytest.fixture
def uncombined_sample_parser(sample_report_path: Path) -> CpuzTxtParser:
    """Initialized CpuzTxtParser from sample_report.txt with auto_combine_slots disabled."""
    return CpuzTxtParser(str(sample_report_path), auto_combine_slots=False)


def _render_rich_text(info: SystemInfo) -> str:
    """Render a SystemInfo object with Rich into a plain captured text string."""
    from rich.console import Console

    console = Console(record=True, width=120)
    exporters.to_rich(info, console=console)
    return console.export_text()


class TestToPlain:
    """Test plain-text serialization."""

    def test_renders_full_hardware_report(self, sample_parser: CpuzTxtParser) -> None:
        """Verify to_plain renders all populated hardware sections and combined RAM slots."""
        expected = (
            'Motherboard: DUMMY Vendor Corp DUMMY Mainboard Model\n'
            'BIOS: DUMMY_BIOS_CORP V1.0.0 01/01/2025\n'
            'CPU: DUMMY Processor Model 8-Core\n'
            'Memory: 16GB\n'
            '2x DDR4 2666MHz 8GB DUMMY_MEM_CORP\n'
            'Graphics: DUMMY Graphics Adapter\n'
            'Operating System: DUMMY Operating System 64-bit\n'
        )
        assert exporters.to_plain(sample_parser) == expected

    def test_renders_empty_hardware_report(self) -> None:
        """Verify to_plain renders labeled empty sections when no hardware data is populated."""
        expected = (
            'Motherboard: \n'
            'BIOS: \n'
            'CPU: \n'
            'Memory: \n'
            'Graphics: \n'
            'Operating System: \n'
        )
        assert exporters.to_plain(SystemInfo()) == expected

    def test_renders_uncombined_ram_slots_without_count_prefix(
        self,
        uncombined_sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify uncombined RAM slot dicts render as individual plain lines without counts."""
        result = exporters.to_plain(uncombined_sample_parser)
        assert result.count('DDR4 2666MHz 8GB DUMMY_MEM_CORP') == 2
        assert '2x ' not in result
        assert '{' not in result


class TestToRich:
    """Test Rich panel and table rendering."""

    @pytest.mark.skipif(not FEATURE_RICH, reason='rich is not installed')
    def test_renders_all_sections_and_values_to_provided_console(
        self,
        sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify to_rich renders all section titles along with the parsed hardware values."""
        captured = _render_rich_text(sample_parser)
        expected_snippets = (
            'Motherboard',
            'DUMMY Vendor Corp',
            'DUMMY Mainboard Model',
            'BIOS',
            'DUMMY_BIOS_CORP',
            'V1.0.0',
            '01/01/2025',
            'Processor (CPU)',
            'DUMMY Processor Model 8-Core',
            'RAM Memory — Total Detected: 16GB',
            'Installed RAM Slots',
            '2x DDR4 2666MHz 8GB DUMMY_MEM_CORP',
            'Graphics (GPU)',
            'DUMMY Graphics Adapter',
            'Operating System (OS)',
            'DUMMY Operating System 64-bit',
        )
        for snippet in expected_snippets:
            assert snippet in captured, f'Missing expected snippet {snippet!r} in Rich output'

    @pytest.mark.skipif(not FEATURE_RICH, reason='rich is not installed')
    def test_renders_with_default_console_when_none_provided(
        self,
        sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify calling to_rich without a console creates a default one and prints all 6 blocks."""
        with patch('rich.console.Console.print', autospec=True) as mock_print:
            exporters.to_rich(sample_parser)
            assert mock_print.call_count == 6

    @pytest.mark.skipif(not FEATURE_RICH, reason='rich is not installed')
    def test_renders_na_placeholders_for_empty_data(self) -> None:
        """Verify empty hardware fields display N/A and the empty RAM slots placeholder."""
        captured = _render_rich_text(SystemInfo())
        assert 'N/A' in captured
        assert 'No detailed memory slots found' in captured

    @pytest.mark.skipif(not FEATURE_RICH, reason='rich is not installed')
    def test_renders_uncombined_ram_slots_as_multi_column_table(
        self,
        uncombined_sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify uncombined RAM slot dicts render in a 4-column table with one row per module."""
        captured = _render_rich_text(uncombined_sample_parser)
        for expected in ('Type', 'Bandwidth', 'Size', 'Manufacturer', 'DDR4', '2666MHz', '8GB'):
            assert expected in captured, f'Missing {expected!r} in uncombined RAM table'
        assert captured.count('DUMMY_MEM_CORP') == 2

    def test_raises_import_error_when_rich_feature_disabled(
        self,
        sample_parser: CpuzTxtParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify to_rich raises ImportError with install guidance when Rich is unavailable."""
        monkeypatch.setattr('cpuz_parser.features.FEATURE_RICH', False)
        with pytest.raises(ImportError, match="Rich visualization requires 'rich'"):
            exporters.to_rich(sample_parser)


class TestToJson:
    """Test JSON serialization."""

    def test_serializes_full_report_with_requested_indentation(
        self,
        sample_parser: CpuzTxtParser,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify to_json produces valid indented JSON matching the full system_info dict."""
        output = exporters.to_json(sample_parser, indent=4)
        assert '\n    "motherboard": {' in output
        assert json.loads(output) == expected_sample_system_info


class TestToXml:
    """Test XML serialization."""

    def test_serializes_nested_dicts_and_lists_under_root_tag(
        self,
        sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify to_xml converts nested dicts and list items under the specified root tag."""
        xml_str = exporters.to_xml(sample_parser, root_tag='hardware_report')
        root = ET.fromstring(xml_str)
        assert root.tag == 'hardware_report'
        assert root.findtext('./motherboard/vendor') == 'DUMMY Vendor Corp'
        assert root.findtext('./bios/version') == 'V1.0.0'
        assert [el.text for el in root.findall('./cpu/item')] == ['DUMMY Processor Model 8-Core']
        assert [el.text for el in root.findall('./ram/slots/item')] == [
            '2x DDR4 2666MHz 8GB DUMMY_MEM_CORP'
        ]

    def test_serializes_none_values_as_empty_elements(self) -> None:
        """Verify None values in system info serialize as empty XML elements rather than 'None'."""
        info = SystemInfo()
        info.update_system_info({'optional_field': None})
        root = ET.fromstring(exporters.to_xml(info))
        elem = root.find('./optional_field')
        assert elem is not None
        assert elem.text is None


class TestToYaml:
    """Test YAML serialization."""

    @pytest.mark.skipif(not FEATURE_YAML, reason='pyyaml is not installed')
    def test_serializes_valid_yaml_matching_system_info(
        self,
        sample_parser: CpuzTxtParser,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify to_yaml outputs valid YAML that round-trips to the expected system_info dict."""
        import yaml  # type: ignore[import-untyped]

        yaml_str = exporters.to_yaml(sample_parser)
        assert yaml.safe_load(yaml_str) == expected_sample_system_info

    def test_raises_import_error_when_yaml_feature_disabled(
        self,
        sample_parser: CpuzTxtParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify to_yaml raises ImportError when pyyaml is unavailable."""
        monkeypatch.setattr('cpuz_parser.features.FEATURE_YAML', False)
        with pytest.raises(ImportError, match='YAML export feature is disabled'):
            exporters.to_yaml(sample_parser)


class TestToToml:
    """Test TOML serialization."""

    @pytest.mark.skipif(not FEATURE_TOML, reason='tomli-w is not installed')
    def test_serializes_valid_toml_matching_system_info(
        self,
        sample_parser: CpuzTxtParser,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify to_toml outputs valid TOML that round-trips to the expected system_info dict."""
        toml_str = exporters.to_toml(sample_parser)
        assert tomllib.loads(toml_str) == expected_sample_system_info

    @pytest.mark.skipif(not FEATURE_TOML, reason='tomli-w is not installed')
    def test_serializes_uncombined_ram_slots_as_toml_tables(
        self,
        uncombined_sample_parser: CpuzTxtParser,
    ) -> None:
        """Verify uncombined RAM slot dicts serialize as valid TOML array-of-tables entries."""
        toml_str = exporters.to_toml(uncombined_sample_parser)
        parsed = tomllib.loads(toml_str)
        expected_slot = {
            'type': 'DDR4',
            'bandwidth': '2666MHz',
            'size': '8GB',
            'manufacturer': 'DUMMY_MEM_CORP',
        }
        assert parsed['ram']['slots'] == [expected_slot, expected_slot]

    def test_raises_import_error_when_toml_feature_disabled(
        self,
        sample_parser: CpuzTxtParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify to_toml raises ImportError when tomli-w is unavailable."""
        monkeypatch.setattr('cpuz_parser.features.FEATURE_TOML', False)
        with pytest.raises(ImportError, match='TOML export feature is disabled'):
            exporters.to_toml(sample_parser)

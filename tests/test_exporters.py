"""Unit tests for cpuz_parser exporters."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from cpuz_parser import exporters
from cpuz_parser.features import FEATURE_TOML, FEATURE_YAML
from cpuz_parser.parsers import CpuzTxtParser, SystemInfo


pytestmark = pytest.mark.unit


class EmptySystemInfo(SystemInfo):
    """SystemInfo instance with default empty values."""


class TestToPlain:
    """Test plain text serialization."""

    def test_to_plain_full_data(self, sample_parser: CpuzTxtParser) -> None:
        result = exporters.to_plain(sample_parser)
        assert 'Motherboard: DUMMY Vendor Corp DUMMY Mainboard Model' in result
        assert 'BIOS: DUMMY_BIOS_CORP V1.0.0 01/01/2025' in result
        assert 'CPU: DUMMY Processor Model 8-Core' in result
        assert 'Memory: 16GB' in result
        assert 'Graphics: DUMMY Graphics Adapter' in result
        assert 'Operating System: DUMMY Operating System 64-bit' in result

    def test_to_plain_empty_data(self) -> None:
        info = EmptySystemInfo()
        result = exporters.to_plain(info)
        assert 'Motherboard: \n' in result or 'Motherboard: ' in result
        assert 'CPU: \n' in result or 'CPU: ' in result

    def test_to_plain_uncombined_slots(self, sample_report_path: Path) -> None:
        parser = CpuzTxtParser(str(sample_report_path), auto_combine_slots=False)
        result = exporters.to_plain(parser)
        assert result.count('DDR4 2666MHz 8GB DUMMY_MEM_CORP') == 2
        assert '2x ' not in result
        assert '{' not in result


class TestToRich:
    """Test Rich rendering."""

    def test_to_rich_with_provided_console(self, sample_parser: CpuzTxtParser) -> None:
        console = Console(record=True, width=120)
        exporters.to_rich(sample_parser, console=console)
        captured = console.export_text()
        assert 'Motherboard & BIOS' in captured
        assert 'Processor (CPU)' in captured
        assert 'Memory (RAM)' in captured
        assert 'Graphics (GPU)' in captured
        assert 'Operating System' in captured

    def test_to_rich_with_default_console(self, sample_parser: CpuzTxtParser) -> None:
        with patch('rich.console.Console.print') as mock_print:
            exporters.to_rich(sample_parser)
            assert mock_print.call_count >= 5

    def test_to_rich_with_empty_data(self) -> None:
        info = EmptySystemInfo()
        console = Console(record=True, width=120)
        exporters.to_rich(info, console=console)
        captured = console.export_text()
        assert 'N/A' in captured
        assert 'No detailed memory slots found' in captured

    def test_to_rich_uncombined_slots_multi_column(self, sample_report_path: Path) -> None:
        parser = CpuzTxtParser(str(sample_report_path), auto_combine_slots=False)
        console = Console(record=True, width=120)
        exporters.to_rich(parser, console=console)
        captured = console.export_text()
        for header in ('Type', 'Bandwidth', 'Size', 'Manufacturer'):
            assert header in captured
        assert captured.count('DUMMY_MEM_CORP') == 2

    def test_to_rich_disabled_feature(self, sample_parser: CpuzTxtParser) -> None:
        with patch('cpuz_parser.features.FEATURE_RICH', False), pytest.raises(ImportError, match="Rich visualization requires 'rich'"):
            exporters.to_rich(sample_parser)


class TestToJson:
    """Test JSON serialization."""

    def test_to_json_valid_and_indented(self, sample_parser: CpuzTxtParser) -> None:
        output = exporters.to_json(sample_parser, indent=4)
        parsed = json.loads(output)
        assert parsed['motherboard']['vendor'] == 'DUMMY Vendor Corp'
        assert parsed['cpu'] == ['DUMMY Processor Model 8-Core']


class TestToXml:
    """Test XML serialization."""

    def test_to_xml_structure(self, sample_parser: CpuzTxtParser) -> None:
        xml_str = exporters.to_xml(sample_parser, root_tag='system_info')
        root = ET.fromstring(xml_str)
        assert root.tag == 'system_info'
        vendor_elem = root.find('./motherboard/vendor')
        assert vendor_elem is not None
        assert vendor_elem.text == 'DUMMY Vendor Corp'

    def test_build_xml_element_with_none_value(self) -> None:
        elem = exporters._build_xml_element('test_tag', None)
        assert elem.tag == 'test_tag'
        assert elem.text == ''


class TestToYaml:
    """Test YAML serialization."""

    def test_to_yaml_output(self, sample_parser: CpuzTxtParser) -> None:
        if not FEATURE_YAML:
            pytest.skip("YAML dependency not installed")
        yaml_str = exporters.to_yaml(sample_parser)
        assert 'motherboard:' in yaml_str
        assert 'DUMMY Vendor Corp' in yaml_str

    def test_to_yaml_disabled_feature(self, sample_parser: CpuzTxtParser) -> None:
        with patch('cpuz_parser.features.FEATURE_YAML', False), pytest.raises(ImportError, match="YAML export feature is disabled"):
            exporters.to_yaml(sample_parser)


class TestToToml:
    """Test TOML serialization."""

    def test_to_toml_output(self, sample_parser: CpuzTxtParser) -> None:
        if not FEATURE_TOML:
            pytest.skip("TOML dependency not installed")
        toml_str = exporters.to_toml(sample_parser)
        assert '[motherboard]' in toml_str
        assert 'DUMMY Vendor Corp' in toml_str

    def test_to_toml_disabled_feature(self, sample_parser: CpuzTxtParser) -> None:
        with patch('cpuz_parser.features.FEATURE_TOML', False), pytest.raises(ImportError, match="TOML export feature is disabled"):
            exporters.to_toml(sample_parser)

"""Unit tests for SystemInfo and CpuzTxtParser."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from cpuz_parser.parsers import CpuzTxtParser, SystemInfo


if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.unit


class ConcreteSystemInfo(SystemInfo):
    """Concrete implementation of SystemInfo ABC for testing base behavior."""


class TestSystemInfo:
    """Test the SystemInfo abstract base class and helper methods."""

    def test_default_initialization(self) -> None:
        info = ConcreteSystemInfo()
        expected = {
            'motherboard': {'vendor': '', 'model': ''},
            'bios': {'vendor': '', 'version': '', 'date': ''},
            'cpu': [],
            'ram': {'size': '', 'slots': []},
            'gpu': [],
            'os': [],
        }
        assert info.system_info == expected

    def test_update_system_info(self) -> None:
        info = ConcreteSystemInfo()
        info.update_system_info({'custom_field': 42})
        assert info._system_info['custom_field'] == 42

    def test_system_info_deepcopy(self) -> None:
        info = ConcreteSystemInfo()
        data1 = info.system_info
        data1['cpu'].append('Custom CPU')
        assert info.system_info['cpu'] == []

    def test_count_slots_aggregation_and_ordering(self) -> None:
        raw_slots = [
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
            {'type': 'DDR4', 'bandwidth': '2666MHz', 'size': '4GB', 'manufacturer': 'Kingston'},
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
        ]
        counted = SystemInfo.count_slots(raw_slots)
        assert counted == [
            '1x DDR4 2666MHz 4GB Kingston',
            '2x DDR4 3200MHz 8GB Corsair',
        ]

    def test_str_representation(self) -> None:
        info = ConcreteSystemInfo()
        info._system_info['motherboard']['vendor'] = 'ASUS'
        info._system_info['motherboard']['model'] = 'ROG'
        rendered = str(info)
        assert 'Motherboard: ASUS ROG' in rendered


class TestCpuzTxtParserInit:
    """Test CpuzTxtParser initialization with various input types."""

    def test_init_none_file(self) -> None:
        parser = CpuzTxtParser()
        assert parser.ram_freq_translate == {}
        assert not hasattr(parser, 'txt_content')
        assert parser.system_info['cpu'] == []

    def test_init_binary_stream(self, sample_report_content: str) -> None:
        bio = io.BytesIO(sample_report_content.encode('cp1252'))
        parser = CpuzTxtParser(bio)
        assert parser.system_info['cpu'] == ['DUMMY Processor Model 8-Core']

    def test_init_file_path_str(self, sample_report_path: Path) -> None:
        parser = CpuzTxtParser(str(sample_report_path))
        assert parser.system_info['motherboard']['vendor'] == 'DUMMY Vendor Corp'

    def test_init_with_ram_freq_translate(
        self,
        sample_report_path: Path,
    ) -> None:
        parser = CpuzTxtParser(
            str(sample_report_path),
            ram_freq_translate={'2666': 'DDR4-2666-CUSTOM'},
        )
        assert parser.ram_freq_translate == {'2666': 'DDR4-2666-CUSTOM'}
        slots_str = ' '.join(parser.system_info['ram']['slots'])
        assert 'DDR4-2666-CUSTOMMHz' in slots_str


class TestCpuzTxtParserIsolatedMethods:
    """Test individual parsing methods of CpuzTxtParser in complete isolation."""

    def test_parse_motherboard_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['motherboard']
        parser.parse_motherboard()
        assert parser._system_info['motherboard']['vendor'] == 'DUMMY Vendor Corp'
        assert parser._system_info['motherboard']['model'] == 'DUMMY Mainboard Model'

    def test_parse_motherboard_missing(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'Empty text with no baseboard header\n'
        parser.parse_motherboard()
        assert parser._system_info['motherboard']['vendor'] == ''
        assert parser._system_info['motherboard']['model'] == ''

    def test_parse_bios_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['bios']
        parser.parse_bios()
        assert parser._system_info['bios']['vendor'] == 'DUMMY_BIOS_CORP'
        assert parser._system_info['bios']['version'] == 'V1.0.0'
        assert parser._system_info['bios']['date'] == '01/01/2025'

    def test_parse_bios_missing(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'No BIOS section\n'
        parser.parse_bios()
        assert parser._system_info['bios']['vendor'] == ''
        assert parser._system_info['bios']['version'] == ''
        assert parser._system_info['bios']['date'] == ''

    def test_parse_cpu_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['cpu']
        parser.parse_cpu()
        assert parser._system_info['cpu'] == ['DUMMY Processor Model 8-Core']

    def test_parse_cpu_missing(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'No Processor section\n'
        parser.parse_cpu()
        assert parser._system_info['cpu'] == []

    def test_parse_ram_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['ram']
        parser.parse_ram()
        assert parser._system_info['ram']['size'] == '16GB'
        assert len(parser._system_info['ram']['slots']) == 2

    def test_parse_ram_missing_chipset(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'No chipset section\n'
        parser.parse_ram()
        assert parser._system_info['ram']['size'] == ''
        assert parser._system_info['ram']['slots'] == []

    def test_parse_ram_chipset_without_memory_size(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'Chipset\n-----------------------\nNorthbridge test\n'
        parser.parse_ram()
        assert parser._system_info['ram']['size'] == ''

    def test_parse_gpu_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['gpu']
        parser.parse_gpu()
        assert parser._system_info['gpu'] == ['DUMMY Graphics Adapter']

    def test_parse_gpu_missing(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'No GPU section\n'
        parser.parse_gpu()
        assert parser._system_info['gpu'] == []

    def test_parse_os_isolated(self, section_contents: dict[str, str]) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = section_contents['os']
        parser.parse_os()
        assert parser._system_info['os'] == ['DUMMY Operating System 64-bit']

    def test_parse_os_missing(self) -> None:
        parser = CpuzTxtParser()
        parser.txt_content = 'No OS section\n'
        parser.parse_os()
        assert parser._system_info['os'] == []


class TestTransformRamSlot:
    """Test edge cases and transformations in `_format_ram_slot`."""

    @pytest.mark.parametrize(
        ('raw_size', 'expected_size'),
        [
            ('1024 MBytes', '1GB'),
            ('8192 MBytes', '8GB'),
            ('1536 MBytes', '1.5GB'),
            ('512 MBytes', '0.5GB'),
            ('invalid', 'invalid'),
        ],
    )
    def test_size_transformations(self, raw_size: str, expected_size: str) -> None:
        parser = CpuzTxtParser()
        slot = {
            'type': 'DDR4',
            'bandwidth': 'DDR4-2666 (1333 MHz)',
            'size': raw_size,
            'manufacturer': 'DUMMY_MFG',
        }
        transformed = parser._format_ram_slot(slot)
        assert transformed['size'] == expected_size

    @pytest.mark.parametrize(
        ('raw_mfg', 'expected_mfg'),
        [
            ('Corsair (7F7F)', 'Corsair'),
            ('Kingston (0102)', 'Kingston'),
            ('Crucial', 'Crucial'),
        ],
    )
    def test_manufacturer_regex_strip(self, raw_mfg: str, expected_mfg: str) -> None:
        parser = CpuzTxtParser()
        slot = {
            'type': 'DDR4',
            'bandwidth': 'DDR4-2666 (1333 MHz)',
            'size': '8192 MBytes',
            'manufacturer': raw_mfg,
        }
        transformed = parser._format_ram_slot(slot)
        assert transformed['manufacturer'] == expected_mfg

    def test_bandwidth_regex_matched_and_translated(self) -> None:
        parser = CpuzTxtParser(ram_freq_translate={'2666': 'DDR4-2666-CUSTOM'})
        slot = {
            'type': 'DDR4',
            'bandwidth': 'DDR4-2666 (1333 MHz)',
            'size': '8192 MBytes',
            'manufacturer': 'DUMMY',
        }
        transformed = parser._format_ram_slot(slot)
        assert transformed['bandwidth'] == 'DDR4-2666-CUSTOMMHz'

    def test_bandwidth_regex_matched_without_translation(self) -> None:
        parser = CpuzTxtParser()
        slot = {
            'type': 'DDR4',
            'bandwidth': 'PC4-21300 (1333 MHz)',
            'size': '8192 MBytes',
            'manufacturer': 'DUMMY',
        }
        transformed = parser._format_ram_slot(slot)
        assert transformed['bandwidth'] == '2666MHz'

    def test_bandwidth_regex_not_matching(self) -> None:
        parser = CpuzTxtParser()
        slot = {
            'type': 'DDR4',
            'bandwidth': 'Unknown Bandwidth Format',
            'size': '8192 MBytes',
            'manufacturer': 'DUMMY',
        }
        transformed = parser._format_ram_slot(slot)
        assert transformed['bandwidth'] == 'Unknown Bandwidth Format'

    def test_bandwidth_value_error_handled(self) -> None:
        parser = CpuzTxtParser()
        slot = {
            'type': 'DDR4',
            'bandwidth': 'DDR4-2666 (1333 MHz)',
            'size': '8192 MBytes',
            'manufacturer': 'DUMMY',
        }
        with patch('builtins.int', side_effect=ValueError):
            transformed = parser._format_ram_slot(slot)
        assert transformed['bandwidth'] == 'DDR4-2666 (1333 MHz)'

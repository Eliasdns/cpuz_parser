"""Unit tests for SystemInfo and CpuzTxtParser."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from cpuz_parser.parsers import CpuzTxtParser, SystemInfo


if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.unit


EMPTY_SYSTEM_INFO = {
    'motherboard': {'vendor': '', 'model': ''},
    'bios': {'vendor': '', 'version': '', 'date': ''},
    'cpu': [],
    'ram': {'size': '', 'slots': []},
    'gpu': [],
    'os': [],
}

EXPECTED_SAMPLE_SYSTEM_INFO = {
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


def _parser_from_text(
    text: str,
    ram_freq_translate: dict[str, str] | None = None,
) -> CpuzTxtParser:
    """Create a CpuzTxtParser from an in-memory text snippet."""
    return CpuzTxtParser(
        io.BytesIO(text.encode('cp1252')),
        ram_freq_translate=ram_freq_translate,
    )


def _parse_single_dimm(
    *,
    mem_type: str = 'DDR4',
    manufacturer: str = 'Corsair (7F7F)',
    size: str = '8192 MBytes',
    bandwidth: str = 'DDR4-2666 (1333 MHz)',
    ram_freq_translate: dict[str, str] | None = None,
) -> list[str]:
    """Parse a minimal DIMM section and return the formatted RAM slots."""
    report = (
        'DIMM #\t\t\t\t0\n'
        f'\tMemory type\t\t{mem_type}\n'
        f'\tModule Manufacturer(ID)\t{manufacturer}\n'
        f'\tSize\t\t\t{size}\n'
        f'\tMax bandwidth\t\t{bandwidth}\n'
    )
    return _parser_from_text(report, ram_freq_translate=ram_freq_translate).system_info['ram']['slots']


class TestSystemInfo:
    """Test SystemInfo base behavior and helper methods."""

    def test_default_initialization(self) -> None:
        info = SystemInfo()
        assert info.system_info == EMPTY_SYSTEM_INFO

    def test_update_system_info(self) -> None:
        info = SystemInfo()
        info.update_system_info({'custom_field': 42})
        assert info.system_info['custom_field'] == 42

    def test_system_info_returns_deepcopy(self) -> None:
        info = SystemInfo()
        snapshot = info.system_info
        snapshot['cpu'].append('Custom CPU')
        snapshot['motherboard']['vendor'] = 'Mutated'
        assert info.system_info == EMPTY_SYSTEM_INFO

    def test_count_slots_aggregation_and_ordering(self) -> None:
        raw_slots = [
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
            {'type': 'DDR4', 'bandwidth': '2666MHz', 'size': '4GB', 'manufacturer': 'Kingston'},
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
        ]
        assert SystemInfo.count_slots(raw_slots) == [
            '1x DDR4 2666MHz 4GB Kingston',
            '2x DDR4 3200MHz 8GB Corsair',
        ]

    def test_str_representation(self) -> None:
        info = SystemInfo()
        info.update_system_info({'motherboard': {'vendor': 'ASUS', 'model': 'ROG'}})
        assert 'Motherboard: ASUS ROG' in str(info)


class TestCpuzTxtParserInit:
    """Test CpuzTxtParser initialization with different input sources."""

    def test_init_without_file(self) -> None:
        parser = CpuzTxtParser()
        assert parser.ram_freq_translate == {}
        assert parser.system_info == EMPTY_SYSTEM_INFO

    def test_init_from_file_path(self, sample_report_path: Path) -> None:
        parser = CpuzTxtParser(str(sample_report_path))
        assert parser.system_info == EXPECTED_SAMPLE_SYSTEM_INFO

    def test_init_from_binary_stream_normalizes_crlf(self, sample_report_content: str) -> None:
        crlf_bytes = sample_report_content.replace('\n', '\r\n').encode('cp1252')
        parser = CpuzTxtParser(io.BytesIO(crlf_bytes))
        assert parser.system_info == EXPECTED_SAMPLE_SYSTEM_INFO

    def test_init_with_ram_freq_translate(self, sample_report_path: Path) -> None:
        parser = CpuzTxtParser(
            str(sample_report_path),
            ram_freq_translate={'2666': '2667'},
        )
        assert parser.system_info['ram']['slots'] == ['2x DDR4 2667MHz 8GB DUMMY_MEM_CORP']


class TestCpuzTxtParserSections:
    """Test parsing of individual CPU-Z report sections."""

    def test_parse_motherboard(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['motherboard'])
        assert parser.system_info['motherboard'] == {
            'vendor': 'DUMMY Vendor Corp',
            'model': 'DUMMY Mainboard Model',
        }

    def test_parse_bios(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['bios'])
        assert parser.system_info['bios'] == {
            'vendor': 'DUMMY_BIOS_CORP',
            'version': 'V1.0.0',
            'date': '01/01/2025',
        }

    def test_parse_cpu(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['cpu'])
        assert parser.system_info['cpu'] == ['DUMMY Processor Model 8-Core']

    def test_parse_multiple_cpus_with_socket_and_processor_headers(self) -> None:
        snippet = (
            'Socket 0 ID = 0\n'
            '\tSpecification\t\tCPU One\n'
            'Processor 1 ID = 1\n'
            '\tSpecification\t\tCPU Two\n'
        )
        parser = _parser_from_text(snippet)
        assert parser.system_info['cpu'] == ['CPU One', 'CPU Two']

    def test_parse_ram(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['ram'])
        assert parser.system_info['ram'] == {
            'size': '16GB',
            'slots': [
                '1x DDR4 2666MHz 8GB DUMMY_MEM_CORP',
                '1x DDR4 3200MHz 8GB DUMMY_MEM_CORP',
            ],
        }

    def test_parse_ram_chipset_without_memory_size(self) -> None:
        parser = _parser_from_text('Chipset\n-----------------------\nNorthbridge test\n')
        assert parser.system_info['ram'] == {'size': '', 'slots': []}

    def test_parse_gpu(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['gpu'])
        assert parser.system_info['gpu'] == ['DUMMY Graphics Adapter']

    def test_parse_os(self, section_contents: dict[str, str]) -> None:
        parser = _parser_from_text(section_contents['os'])
        assert parser.system_info['os'] == ['DUMMY Operating System 64-bit']

    def test_parse_unrecognized_content_leaves_defaults(self) -> None:
        parser = _parser_from_text('Unrecognized report content without valid CPU-Z headers\n')
        assert parser.system_info == EMPTY_SYSTEM_INFO


class TestRamSlotFormatting:
    """Test RAM slot formatting rules (size, manufacturer, and frequency translation)."""

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
    def test_size_formatting(self, raw_size: str, expected_size: str) -> None:
        assert _parse_single_dimm(size=raw_size) == [f'1x DDR4 2666MHz {expected_size} Corsair']

    @pytest.mark.parametrize(
        ('raw_manufacturer', 'expected_manufacturer'),
        [
            ('Corsair (7F7F)', 'Corsair'),
            ('Kingston(0102)', 'Kingston'),
            ('Crucial', 'Crucial'),
        ],
    )
    def test_manufacturer_id_stripping(self, raw_manufacturer: str, expected_manufacturer: str) -> None:
        assert _parse_single_dimm(manufacturer=raw_manufacturer) == [
            f'1x DDR4 2666MHz 8GB {expected_manufacturer}'
        ]

    @pytest.mark.parametrize(
        ('raw_bandwidth', 'freq_map', 'expected_bandwidth'),
        [
            ('PC4-21300 (1333 MHz)', None, '2666MHz'),
            ('PC3-10700 (667 MHz)', {'1334': '1333'}, '1333MHz'),
            ('DDR4-2132 (1066 MHz)', {'2132': '2133'}, '2133MHz'),
            ('DDR4-2134 (1067 MHz)', {'2134': '2133'}, '2133MHz'),
            ('DDR4-2666 (1333 MHz)', {'2132': '2133'}, '2666MHz'),
            ('Unknown Bandwidth Format', None, 'Unknown Bandwidth Format'),
        ],
    )
    def test_bandwidth_formatting_and_translation(
        self,
        raw_bandwidth: str,
        freq_map: dict[str, str] | None,
        expected_bandwidth: str,
    ) -> None:
        assert _parse_single_dimm(bandwidth=raw_bandwidth, ram_freq_translate=freq_map) == [
            f'1x DDR4 {expected_bandwidth} 8GB Corsair'
        ]

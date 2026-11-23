"""Unit tests for SystemInfo and CpuzTxtParser."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import pytest

from cpuz_parser.parsers import CpuzTxtParser, SystemInfo


if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.unit


def _parser_from_text(
    text: str,
    ram_freq_translate: dict[str, str] | None = None,
) -> CpuzTxtParser:
    """Create a CpuzTxtParser from an in-memory cp1252 text snippet."""
    return CpuzTxtParser(
        io.BytesIO(text.encode('cp1252')),
        ram_freq_translate=ram_freq_translate,
    )


class TestSystemInfo:
    """Test SystemInfo base behavior and helper methods."""

    def test_initializes_with_empty_defaults(self, empty_system_info: dict[str, Any]) -> None:
        """Verify SystemInfo initializes all hardware sections with empty defaults."""
        info = SystemInfo()
        assert info.system_info == empty_system_info

    def test_update_system_info_merges_fields(self) -> None:
        """Verify update_system_info merges new entries into the hardware info."""
        info = SystemInfo()
        info.update_system_info({'custom_field': 42})
        info.update_system_info(cpu=['Custom Processor'])
        assert info.system_info['custom_field'] == 42
        assert info.system_info['cpu'][0] == 'Custom Processor'

    def test_system_info_returns_independent_copy(self, empty_system_info: dict[str, Any]) -> None:
        """Verify mutating the dict returned by system_info does not alter internal state."""
        info = SystemInfo()
        snapshot = info.system_info
        snapshot['cpu'].append('Custom CPU')
        snapshot['motherboard']['vendor'] = 'Mutated'
        assert info.system_info == empty_system_info

    def test_count_slots_aggregates_and_sorts(self) -> None:
        """Verify count_slots groups identical RAM modules and returns them sorted."""
        raw_slots = [
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
            {'type': 'DDR4', 'bandwidth': '2666MHz', 'size': '4GB', 'manufacturer': 'Kingston'},
            {'type': 'DDR4', 'bandwidth': '3200MHz', 'size': '8GB', 'manufacturer': 'Corsair'},
        ]
        assert SystemInfo.count_slots(raw_slots) == [
            '1x DDR4 2666MHz 4GB Kingston',
            '2x DDR4 3200MHz 8GB Corsair',
        ]

    # test `__str__` `to_plain(self)`
    def test_str_renders_plain_text_summary(self) -> None:
        """Verify str(info) delegates to plain-text formatting with populated fields."""
        info = SystemInfo()
        info.update_system_info({'motherboard': {'vendor': 'ASUS', 'model': 'ROG'}})
        assert 'Motherboard: ASUS ROG' in str(info)


class TestCpuzTxtParserInit:
    """Test CpuzTxtParser initialization with different input sources."""

    def test_init_without_input_keeps_defaults(self, empty_system_info: dict[str, Any]) -> None:
        """Verify initializing without input keeps empty defaults and no frequency map."""
        parser = CpuzTxtParser()
        assert parser.ram_freq_translate == {}
        assert parser.system_info == empty_system_info

    def test_init_from_file_path(
        self,
        sample_report_path: Path,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify initializing from a file path parses all sections of a CPU-Z report."""
        parser = CpuzTxtParser(str(sample_report_path))
        assert parser.system_info == expected_sample_system_info

    def test_init_from_crlf_binary_stream(
        self,
        sample_report_content: str,
        expected_sample_system_info: dict[str, Any],
    ) -> None:
        """Verify binary streams decode cp1252 and normalize Windows CRLF line endings."""
        crlf_bytes = sample_report_content.replace('\n', '\r\n').encode('cp1252')
        parser = CpuzTxtParser(io.BytesIO(crlf_bytes))
        assert parser.system_info == expected_sample_system_info

    def test_init_applies_ram_freq_translate(self, sample_report_path: Path) -> None:
        """Verify ram_freq_translate maps calculated RAM frequencies during init."""
        parser = CpuzTxtParser(
            str(sample_report_path),
            ram_freq_translate={'2666': '2667'},
        )
        assert parser.system_info['ram']['slots'] == ['2x DDR4 2667MHz 8GB DUMMY_MEM_CORP']


class TestCpuzTxtParserSections:
    """Test parsing of individual CPU-Z report sections."""

    def test_parse_motherboard(self, section_contents: dict[str, str]) -> None:
        """Verify DMI Baseboard vendor and model are extracted from the motherboard section."""
        parser = _parser_from_text(section_contents['motherboard'])
        assert parser.system_info['motherboard'] == {
            'vendor': 'DUMMY Vendor Corp',
            'model': 'DUMMY Mainboard Model',
        }

    def test_parse_bios(self, section_contents: dict[str, str]) -> None:
        """Verify DMI BIOS vendor, version, and date are extracted from the BIOS section."""
        parser = _parser_from_text(section_contents['bios'])
        assert parser.system_info['bios'] == {
            'vendor': 'DUMMY_BIOS_CORP',
            'version': 'V1.0.0',
            'date': '01/01/2025',
        }

    def test_parse_cpu_single(self, section_contents: dict[str, str]) -> None:
        """Verify a single CPU specification is extracted from a Socket header."""
        parser = _parser_from_text(section_contents['cpu'])
        assert parser.system_info['cpu'] == ['DUMMY Processor Model 8-Core']

    def test_parse_cpu_multiple_headers(self) -> None:
        """Verify multiple CPUs are extracted across both Socket and Processor headers."""
        snippet = (
            'Socket 0 ID = 0\n'
            '\tSpecification\t\tCPU One\n'
            'Processor 1 ID = 1\n'
            '\tSpecification\t\tCPU Two\n'
        )
        parser = _parser_from_text(snippet)
        assert parser.system_info['cpu'] == ['CPU One', 'CPU Two']

    def test_parse_ram(self, section_contents: dict[str, str]) -> None:
        """Verify Chipset memory size and DIMM slots are extracted and formatted."""
        parser = _parser_from_text(section_contents['ram'])
        assert parser.system_info['ram'] == {
            'size': '16GB',
            'slots': [
                '1x DDR4 2666MHz 8GB DUMMY_MEM_CORP',
                '1x DDR4 3200MHz 8GB DUMMY_MEM_CORP',
            ],
        }

    def test_parse_ram_without_memory_size(self) -> None:
        """Verify a Chipset section lacking Memory Size leaves RAM fields empty."""
        parser = _parser_from_text('Chipset\n-----------------------\nNorthbridge test\n')
        assert parser.system_info['ram'] == {'size': '', 'slots': []}

    def test_parse_gpu(self, section_contents: dict[str, str]) -> None:
        """Verify display adapter name is extracted from the GPU section."""
        parser = _parser_from_text(section_contents['gpu'])
        assert parser.system_info['gpu'] == ['DUMMY Graphics Adapter']

    def test_parse_os(self, section_contents: dict[str, str]) -> None:
        """Verify Windows version string is extracted from the OS section."""
        parser = _parser_from_text(section_contents['os'])
        assert parser.system_info['os'] == ['DUMMY Operating System 64-bit']

    def test_parse_unrecognized_content_keeps_defaults(self, empty_system_info: dict[str, Any]) -> None:
        """Verify unrecognized text leaves all hardware sections at their empty defaults."""
        parser = _parser_from_text('Unrecognized report content without valid CPU-Z headers\n')
        assert parser.system_info == empty_system_info


class TestRamSlotFormatting:
    """Test RAM slot formatting rules (size, manufacturer, and frequency translation)."""

    @staticmethod
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
    def test_formats_slot_size_to_gb(self, raw_size: str, expected_size: str) -> None:
        """Verify RAM module sizes convert from MBytes to GB or remain unchanged if invalid."""
        assert self._parse_single_dimm(size=raw_size) == [f'1x DDR4 2666MHz {expected_size} Corsair']

    @pytest.mark.parametrize(
        ('raw_manufacturer', 'expected_manufacturer'),
        [
            ('Corsair (7F7F)', 'Corsair'),
            ('Kingston(0102)', 'Kingston'),
            ('Crucial', 'Crucial'),
        ],
    )
    def test_strips_manufacturer_id_suffix(self, raw_manufacturer: str, expected_manufacturer: str) -> None:
        """Verify trailing parenthesized manufacturer IDs are stripped with or without space."""
        assert self._parse_single_dimm(manufacturer=raw_manufacturer) == [
            f'1x DDR4 2666MHz 8GB {expected_manufacturer}'
        ]

    @pytest.mark.parametrize(
        ('raw_bandwidth', 'freq_map', 'expected_bandwidth'),
        [
            pytest.param('PC4-21300 (1333 MHz)', None, '2666MHz', id='pc4_no_translation'),
            pytest.param('PC3-10700 (667 MHz)', {'1334': '1333'}, '1333MHz', id='pc3_667mhz_to_1333mhz'),
            pytest.param('DDR4-2132 (1066 MHz)', {'2132': '2133'}, '2133MHz', id='ddr4_1066mhz_to_2133mhz'),
            pytest.param('DDR4-2134 (1067 MHz)', {'2134': '2133'}, '2133MHz', id='ddr4_1067mhz_to_2133mhz'),
            pytest.param('DDR4-2666 (1333 MHz)', {'2132': '2133'}, '2666MHz', id='ddr4_unmapped_frequency'),
            pytest.param('Unknown Bandwidth Format', None, 'Unknown Bandwidth Format', id='unrecognized_format'),
        ],
    )
    def test_formats_bandwidth_and_translates_frequency(
        self,
        raw_bandwidth: str,
        freq_map: dict[str, str] | None,
        expected_bandwidth: str,
    ) -> None:
        """Verify bandwidth doubling, config-based frequency translation, and raw fallback."""
        assert self._parse_single_dimm(bandwidth=raw_bandwidth, ram_freq_translate=freq_map) == [
            f'1x DDR4 {expected_bandwidth} 8GB Corsair'
        ]

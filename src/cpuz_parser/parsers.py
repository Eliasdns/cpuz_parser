from __future__ import annotations

import re
from abc import ABC
from collections import Counter
from copy import deepcopy
from typing import IO, Any

from .exporters import to_plain


class SystemInfo(ABC):
    def __init__(self, auto_combine_slots: bool = True) -> None:
        self.auto_combine_slots = auto_combine_slots

        self._system_info: dict[str, Any] = {}
        self._system_info['motherboard'] = {}
        self._system_info['motherboard']['vendor'] = ''
        self._system_info['motherboard']['model'] = ''
        # self._system_info['motherboard']['revision'] = ''
        self._system_info['bios'] = {}
        self._system_info['bios']['vendor'] = ''
        self._system_info['bios']['version'] = ''
        self._system_info['bios']['date'] = ''
        self._system_info['cpu'] = []
        self._system_info['ram'] = {}
        self._system_info['ram']['size'] = ''
        self._system_info['ram']['slots'] = []  # 'type', 'bandwidth', 'size', 'manufacturer'
        self._system_info['gpu'] = []
        self._system_info['os'] = []

    def update_system_info(self, *args, **kwargs) -> None:
        return self._system_info.update(*args, **kwargs)

    def __str__(self) -> str:
        return to_plain(self)

    @property
    def system_info(self) -> dict:
        si = deepcopy(self._system_info)
        if self.auto_combine_slots:
            si['ram']['slots'] = self.combine_ram_slots(si['ram']['slots'])
        return si

    @staticmethod
    def combine_ram_slots(old_slots) -> list:
        # TODO: old_slots: list[RamSlotDict]
        slots_counter = Counter([frozenset(x.items()) for x in old_slots])
        new_slots = []
        for key, amount in slots_counter.items():
            slot_values = dict(key)  # RamSlotDict
            new_slots.append(
                f'{amount}x '
                + ' '.join([
                    slot_values['type'],
                    slot_values['bandwidth'],
                    slot_values['size'],
                    slot_values['manufacturer'],
                ])
            )
        return sorted(new_slots)


class CpuzTxtParser(SystemInfo):
    def __init__(
        self,
        txt_file: IO | str | None = None,
        ram_freq_translate: dict[str, str] | None = None,
        auto_combine_slots: bool = True,
    ) -> None:
        super().__init__(auto_combine_slots=auto_combine_slots)

        # ram_freqs_single_mul2_to_friendly_dict
        if ram_freq_translate is not None:
            self.ram_freq_translate = ram_freq_translate
        else:
            self.ram_freq_translate = {}

        if txt_file is not None:
            if hasattr(txt_file, 'read'):
                self.txt_content = txt_file.read().decode('cp1252').replace('\r\n', '\n')
            else:
                with open(txt_file, 'rb') as f:
                    self.txt_content = f.read().decode('cp1252').replace('\r\n', '\n')

            self.parse_motherboard()
            self.parse_bios()
            self.parse_cpu()
            self.parse_ram()
            self.parse_gpu()
            self.parse_os()

    def parse_motherboard(self) -> None:
        self._REGEX_MOTHERBOARD = re.compile(
            r"""
            ^DMI[ ]Baseboard[ \t]*\n                # Sub-header line
            (?:[ \t]+[^\n]*\n)*?                    # Any preceding indented lines in this block
            [ \t]+vendor[ \t]+(?P<vendor>[^\n]*)\n  # Board manufacturer
            [ \t]+model[ \t]+(?P<model>[^\n]*)      # Board model (works with or without trailing newline)
            # [ \t]+revision[ \t]+(?P<revision>[^\n]*)  # Board revision
            """,
            re.MULTILINE | re.VERBOSE,
        )
        match = self._REGEX_MOTHERBOARD.search(self.txt_content)
        if match:
            self._system_info['motherboard']['vendor'] = match.group('vendor').strip()
            self._system_info['motherboard']['model'] = match.group('model').strip()
            # self._system_info['motherboard']['revision'] = match.group('revision').strip()

    def parse_bios(self) -> None:
        self._REGEX_BIOS = re.compile(
            r"""
            ^DMI[ ]BIOS[ \t]*\n                       # Sub-header line
            (?:[ \t]+[^\n]*\n)*?                      # Any preceding indented lines in this block
            [ \t]+vendor[ \t]+(?P<vendor>[^\n]*)\n    # BIOS vendor
            [ \t]+version[ \t]+(?P<version>[^\n]*)\n  # BIOS version
            [ \t]+date[ \t]+(?P<date>[^\n]*)          # BIOS release date
            """,
            re.MULTILINE | re.VERBOSE,
        )
        match = self._REGEX_BIOS.search(self.txt_content)
        if match:
            self._system_info['bios']['vendor'] = match.group('vendor').strip()
            self._system_info['bios']['version'] = match.group('version').strip()
            self._system_info['bios']['date'] = match.group('date').strip()

    def parse_cpu(self) -> None:
        self._REGEX_CPU = re.compile(
            r"""
            ^(?:Socket|Processor)[ ]\d+[ \t]+ID[ ]=[ ]\d+[ \t]*\n  # CPU block header (Socket or Processor)
            (?:[ \t]+[^\n]*\n)*?                                   # Indented fields before Specification
            [ \t]+Specification[ \t]+(?P<cpu>[^\n]*)               # Full CPU model specification
            """,
            re.MULTILINE | re.VERBOSE,
        )
        self._system_info['cpu'] = [
            match.group('cpu').strip()
            for match in self._REGEX_CPU.finditer(self.txt_content)
        ]

    def parse_ram(self) -> None:
        self._REGEX_RAM_SIZE = re.compile(
            r"""
            ^Chipset\n-+\n                        # Top-level Chipset section header and divider
            (?:(?!^-+$)[^\n]*\n)*?                # Lines within Chipset (stops at the next ---... divider)
            ^Memory[ ]Size[ \t]+(?P<size>[^\n]*)  # Total installed memory (e.g., '16 GBytes')
            """,
            re.MULTILINE | re.VERBOSE,
        )
        match = self._REGEX_RAM_SIZE.search(self.txt_content)
        if match:
            self._system_info['ram']['size'] = match.group('size').strip().replace(' GBytes', 'GB')

        self._REGEX_RAM_SLOTS = re.compile(
            r"""
            ^DIMM[ ]\#[ \t]+\d+[ \t]*\n                       # DIMM slot header (supports 2+ digits)
            (?:[ \t]+[^\n]*\n)*?                              # Indented lines before Memory type
            [ \t]+Memory[ ]type[ \t]+(?P<type>[^\n]*)\n       # e.g., DDR3, DDR4, DDR5
            (?:[ \t]+[^\n]*\n)*?                              # Indented lines before Manufacturer
            [ \t]+(?:Module[ ])?Manufacturer[ ]?\(ID\)[ \t]+(?P<manufacturer>[^\n]*)\n  # Module/Manufacturer (ID)
            (?:[ \t]+[^\n]*\n)*?                              # Indented lines before Size
            [ \t]+Size[ \t]+(?P<size>[^\n]*)\n                # Module size (e.g., '8192 MBytes')
            (?:[ \t]+[^\n]*\n)*?                              # Indented lines before Max bandwidth
            [ \t]+Max[ ]bandwidth[ \t]+(?P<bandwidth>[^\n]*)  # Rated speed (e.g., 'DDR4-2666 (1333 MHz)')
            """,
            re.MULTILINE | re.VERBOSE,
        )
        self._system_info['ram']['slots'] = [
            self._format_ram_slot({
                'type': match_slot.group('type').strip(),
                'bandwidth': match_slot.group('bandwidth').strip(),
                'size': match_slot.group('size').strip(),
                'manufacturer': match_slot.group('manufacturer').strip(),
            })
            for match_slot in self._REGEX_RAM_SLOTS.finditer(self.txt_content)
        ]

    # TODO: TypedDict RamSlotDict (dict[str, str | bytes | None])
    # TODO: e definir também um TypedDict (ou dataclass) para `.system_info` e `._system_info`
    def _format_ram_slot(self, slot: dict) -> dict:
        # Format 'size': convert '<integer> MBytes' to '<value>GB'
        if slot['size'].endswith(' MBytes'):
            size_mb_str = slot['size'].removesuffix(' MBytes')
            # isascii() + isdigit() ensures pure ASCII 0-9 (rejecting Unicode digits like '²', negatives, 'inf'/'nan'),
            # so int(...) is guaranteed safe
            if size_mb_str.isascii() and size_mb_str.isdigit():
                size_gb_str = str(int(size_mb_str) / 1024).removesuffix('.0')
                slot['size'] = f'{size_gb_str}GB'

        # Format 'manufacturer': strip trailing parenthesized JEDEC ID

        # Trailing parenthesized JEDEC ID on RAM manufacturer names (e.g., 'Corsair (7F7F)' -> 'Corsair')
        self._REGEX_RAM_MANUFACTURER = re.compile(
            r'[ ]?[(]\w+[)]$'
        )

        slot['manufacturer'] = self._REGEX_RAM_MANUFACTURER.sub('', slot['manufacturer'])

        # Format 'bandwidth': double single-rate MHz clock (validated as ASCII digits by [0-9]+)
        # and apply optional friendly frequency mapping

        # Rated RAM bandwidth strings (e.g., 'PC4-21300 (1333 MHz)', 'PC3L-12800 (800 MHz)', 'DDR4-2666 (1333 MHz)').
        # Captures the single-rate clock in ASCII digits ([0-9]+), so int(...) is guaranteed safe
        self._REGEX_RAM_BANDWIDTH = re.compile(
            r'^(?:PC|DDR)\w*-[0-9]+.* [(](?P<bandwidth>[0-9]+) MHz[)]$'
        )

        match_bandwidth = self._REGEX_RAM_BANDWIDTH.match(slot['bandwidth'])
        if match_bandwidth:
            freq = str(int(match_bandwidth.group('bandwidth')) * 2)
            slot['bandwidth'] = f'{self.ram_freq_translate.get(freq, freq)}MHz'

        return slot

    def parse_gpu(self) -> None:
        self._REGEX_GPU = re.compile(
            r"""
            ^Display[ ]adapter[ ]\d+(?:[ ]\([a-z]+\))?[ \t]*\n  # Display adapter header (optional '(primary)' suffix)
            (?:[ \t]+[^\n]*\n)*?                                # Indented fields before Name
            [ \t]+Name[ \t]+(?P<gpu>[^\n]*)                     # GPU adapter name
            """,
            re.MULTILINE | re.VERBOSE,
        )
        self._system_info['gpu'] = [
            match.group('gpu').strip()
            for match in self._REGEX_GPU.finditer(self.txt_content)
        ]

    def parse_os(self) -> None:
        # Top-level Windows Version line under the Software section
        self._REGEX_OS = re.compile(
            r'^Windows[ ]Version[ \t]+(?P<os>[^\n]*)', re.MULTILINE
        )

        match = self._REGEX_OS.search(self.txt_content)
        if match:
            # self._system_info['os'] = [match.group('os').replace('  ', ' ').replace('   ', ' ')]
            # Keep raw internal spacing (e.g., before '(Build ...)') as reported by CPU-Z;
            # collapsing spaces like `.replace('  ', ' ')` is intentionally not applied.
            self._system_info['os'] = [match.group('os').strip()]

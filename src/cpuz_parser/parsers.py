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
        regex_motherboard = re.compile(r"""
            ^DMI[ ]Baseboard\s*$  # Header secundário
            (.|\n)*?  # DOTALL não guloso
            ^\s+vendor\s+(?P<vendor>.*)\n
            ^\s+model\s+(?P<model>.*)\n
            # ^\s+revision\s+(?P<revision>.*)$
        """, re.MULTILINE | re.VERBOSE)

        match = regex_motherboard.search(self.txt_content)
        if match:
            match_motherboard_dict = match.groupdict()
            self._system_info['motherboard']['vendor'] = match_motherboard_dict['vendor'].strip()
            self._system_info['motherboard']['model'] = match_motherboard_dict['model'].strip()
            # self._system_info['motherboard']['revision'] = match_motherboard_dict['revision'].strip()

    def parse_bios(self) -> None:
        regex_bios = re.compile(r"""
            # ^DMI\n-+$  # Header principal
            # (?s:.*?)(?!^-+)  # Não funcionando corretamento, ainda dando match caso (^-+) anteceda Header secundário
            ^DMI[ ]BIOS\s*$  # Header secundário
            # (?s:.*?)(?!^\S)  # De mesmo modo, não funcionando corretamento
            # (?s:.*?)  # DOTALL não guloso
            (.|\n)*?  # DOTALL não guloso
            ^\s+vendor\s+(?P<vendor>.*)\n
            ^\s+version\s+(?P<version>.*)\n
            ^\s+date\s+(?P<date>.*)$
        """, re.MULTILINE | re.VERBOSE)

        match = regex_bios.search(self.txt_content)
        if match:
            match_bios_dict = match.groupdict()
            self._system_info['bios']['vendor'] = match_bios_dict['vendor'].strip()
            self._system_info['bios']['version'] = match_bios_dict['version'].strip()
            self._system_info['bios']['date'] = match_bios_dict['date'].strip()

    def parse_cpu(self) -> None:
        regex_cpu = re.compile(r"""
            ^(Socket|Processor)[ ]\d+\s+ID[ ]=[ ]\d+$  # Header secundário
            (.|\n)*?  # DOTALL não guloso
            # ^\s+Name\s+(?P<cpu>.*)$
            ^\s+Specification\s+(?P<cpu>.*)$
        """, re.MULTILINE | re.VERBOSE)

        self._system_info['cpu'] = [
            x.groupdict()['cpu'].strip()
            for x in regex_cpu.finditer(self.txt_content)
        ]

    def parse_ram(self) -> None:
        regex_ram_size = re.compile(r"""
            ^Chipset\n-+$  # Header
            (.|\n)*?  # DOTALL não guloso
            ^Memory[ ]Size\s+(?P<size>.*)$
        """, re.MULTILINE | re.VERBOSE)

        match = regex_ram_size.search(self.txt_content)
        if match:
            self._system_info['ram']['size'] = match.groupdict()['size'].replace(' GBytes', 'GB')

        regex_ram_slots = re.compile(r"""
            ^DIMM[ ]\#\s+\d\s*$  # Header secundário
            (.|\n)*?  # DOTALL não guloso
            ^\s+Memory[ ]type\s+(?P<type>.*)$
            (.|\n)*?  # DOTALL não guloso
            ^\s+(Module[ ])?Manufacturer[ ]?[(]ID[)]\s+(?P<manufacturer>.*)$
            (.|\n)*?  # DOTALL não guloso
            ^\s+Size\s+(?P<size>.*)$
            (.|\n)*?  # DOTALL não guloso
            ^\s+Max[ ]bandwidth\s+(?P<bandwidth>.*)$
        """, re.MULTILINE | re.VERBOSE)

        self._system_info['ram']['slots'] = []
        for slots in regex_ram_slots.finditer(self.txt_content):
            match_slots_dict = slots.groupdict()
            self._system_info['ram']['slots'].append(self._format_ram_slot({
                'type': match_slots_dict['type'].strip(),
                'bandwidth': match_slots_dict['bandwidth'].strip(),
                'size':  match_slots_dict['size'].strip(),
                'manufacturer': match_slots_dict['manufacturer'].strip(),
            }))

    # TODO: TypedDict RamSlotDict (dict[str, str | bytes | None])
    # TODO: e definir também um TypedDict (ou dataclass) para `.system_info` e `._system_info`
    # Format 'bandwidth', 'size' and 'manufacturer' fields
    def _format_ram_slot(self, slot: dict) -> dict:
        # Format 'size'
        try:
            slot['size'] = str(float( slot['size'].replace(' MBytes', '') ) / 1024)
            slot['size'] = slot['size'].replace('.0', '') if slot['size'].endswith('.0') else slot['size']
            slot['size'] += 'GB'
        # TODO: investigar o por que desse try-except (seria pelo casting com float?)
        except ValueError:
            pass

        # Format 'manufacturer'
        regex_manufacturer = re.compile(
            r"[ ]?[(]\w+[)]$"
        )
        slot['manufacturer'] = re.sub(regex_manufacturer, '', slot['manufacturer'])

        # Format 'bandwidth'
        regex_bandwidth = re.compile(
            r"^(PC.|DDR.)-[0-9]+.* [(](?P<bandwidth>[0-9]+) MHz[)]$"
        )
        match = regex_bandwidth.match(slot['bandwidth'])
        if match:
            try:
                slot['bandwidth'] = str(int(match.groupdict()['bandwidth']) * 2)
                if slot['bandwidth'] in self.ram_freq_translate:
                    # ram_freqs_single_mul2_to_friendly_dict
                    slot['bandwidth'] = self.ram_freq_translate[ slot['bandwidth'] ]
                slot['bandwidth'] += 'MHz'
            # TODO: investigar o por que desse try-except (seria pelo casting com int?)
            except ValueError:  # pragma: no cover
                pass

        return slot

    def parse_gpu(self) -> None:
        regex_gpu = re.compile(r"""
            ^Display[ ]adapter[ ]\d[ ]?([(][a-z]+[)])?\s*$  # Header secundário
            (.|\n)*?  # DOTALL não guloso
            ^\s+Name\s+(?P<gpu>.*)$
        """, re.MULTILINE | re.VERBOSE)

        self._system_info['gpu'] = [
            x.groupdict()['gpu'].strip()
            for x in regex_gpu.finditer(self.txt_content)
        ]

    def parse_os(self) -> None:
        regex_os = re.compile(r"""
            ^Windows[ ]Version  # Header secundário
            \s+(?P<os>.*)$
        """, re.MULTILINE | re.VERBOSE)

        match = regex_os.search(self.txt_content)
        if match:
            # self._system_info['os'] = [ match.groupdict()['os'].replace('  ', ' ').replace('   ', ' ') ]
            self._system_info['os'] = [ match.groupdict()['os'].strip() ]

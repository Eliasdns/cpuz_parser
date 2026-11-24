"""Data serializers and formatters for cpuz_parser."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any

from .features import (
    require_rich_feature,
    require_toml_feature,
    require_yaml_feature,
)


if TYPE_CHECKING:
    from .parsers import SystemInfo


def _format_slot_plain_text(slot: str | dict[str, str]) -> str:
    """Format a RAM slot entry (either combined string or raw dict) as plain text."""
    if isinstance(slot, dict):
        return ' '.join(filter(None, (
            slot.get('type', ''),
            slot.get('bandwidth', ''),
            slot.get('size', ''),
            slot.get('manufacturer', ''),
        )))
    return slot


def to_plain(si: SystemInfo) -> str:
    """Serialize system info to human-readable plain text."""
    data = si.system_info
    lines: list[str] = []

    mb_parts = ' '.join(filter(None, (
        data['motherboard']['vendor'], data['motherboard']['model']
    )))
    lines.append(f'Motherboard: {mb_parts}')

    bios_parts = ' '.join(filter(None, (
        data['bios']['vendor'], data['bios']['version'], data['bios']['date']
    )))
    lines.append(f'BIOS: {bios_parts}')

    lines.append(f"CPU: {' + '.join(data['cpu'])}")
    lines.append(f"Memory: {data['ram']['size']}")
    for slot in data['ram']['slots']:
        lines.append(_format_slot_plain_text(slot))
    lines.append(f"Graphics: {' + '.join(data['gpu'])}")
    lines.append(f"Operating System: {' + '.join(data['os'])}")

    return '\n'.join(lines) + '\n'


def to_rich(si: SystemInfo, console: Any = None) -> None:
    """Render system hardware information using Rich panels and tables."""
    require_rich_feature()
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    if console is None:
        console = Console()

    data = si.system_info

    # Motherboard & BIOS
    mb_lines = [
        f"[bold cyan]Vendor:[/bold cyan] {data['motherboard']['vendor'] or 'N/A'}",
        f"[bold cyan]Model:[/bold cyan]  {data['motherboard']['model'] or 'N/A'}",
        f"[bold cyan]BIOS:[/bold cyan]   {data['bios']['vendor']} {data['bios']['version']} ({data['bios']['date']})",
    ]
    console.print(Panel('\n'.join(mb_lines), title='[bold green]Motherboard & BIOS[/bold green]', expand=False))

    # Processor (CPU)
    cpus = data.get('cpu', [])
    cpu_text = '\n'.join(f'[bold yellow]•[/bold yellow] {cpu}' for cpu in cpus) if cpus else 'N/A'
    console.print(Panel(cpu_text, title='[bold green]Processor (CPU)[/bold green]', expand=False))

    # Memory (RAM)
    ram_info = data.get('ram', {})
    total_size = ram_info.get('size', 'N/A')
    slots = ram_info.get('slots', [])

    ram_table = Table(
        title=f'Memory (RAM) — Total Detected: {total_size}',
        show_header=True,
        header_style='bold magenta',
    )

    if slots and isinstance(slots[0], dict):
        ram_table.add_column('Type', style='white')
        ram_table.add_column('Bandwidth', style='cyan')
        ram_table.add_column('Size', style='green')
        ram_table.add_column('Manufacturer', style='white')
        for slot in slots:
            ram_table.add_row(
                slot.get('type', '') or 'N/A',
                slot.get('bandwidth', '') or 'N/A',
                slot.get('size', '') or 'N/A',
                slot.get('manufacturer', '') or 'N/A',
            )
    else:
        ram_table.add_column('Installed Modules / Slots', style='white')
        if slots:
            for slot in slots:
                ram_table.add_row(slot)
        else:
            ram_table.add_row('[dim]No detailed memory slots found[/dim]')
    console.print(ram_table)

    # Graphics (GPU)
    gpus = data.get('gpu', [])
    gpu_text = '\n'.join(f'[bold yellow]•[/bold yellow] {gpu}' for gpu in gpus) if gpus else 'N/A'
    console.print(Panel(gpu_text, title='[bold green]Graphics (GPU)[/bold green]', expand=False))

    # Operating System
    os_info = data.get('os', [])
    os_text = '\n'.join(os_info) if os_info else 'N/A'
    console.print(Panel(os_text, title='[bold green]Operating System[/bold green]', expand=False))


def to_json(si: SystemInfo, indent: int = 2) -> str:
    """Serialize system info data to formatted JSON."""
    data = si.system_info
    return json.dumps(data, indent=indent, ensure_ascii=False)


def _build_xml_element(tag: str, value: Any) -> ET.Element:
    """Recursively convert nested dicts, lists, and primitives into XML elements."""
    elem = ET.Element(tag)
    if isinstance(value, dict):
        for k, v in value.items():
            elem.append(_build_xml_element(str(k), v))
    elif isinstance(value, list):
        for item in value:
            elem.append(_build_xml_element('item', item))
    else:
        elem.text = '' if value is None else str(value)
    return elem


def to_xml(si: SystemInfo, root_tag: str = 'system_info') -> str:
    """Serialize system info data to formatted XML."""
    data = si.system_info
    root = _build_xml_element(root_tag, data)
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8').decode('utf-8')


def to_yaml(si: SystemInfo) -> str:
    """Serialize system info data to YAML format."""
    require_yaml_feature()
    import yaml  # type: ignore[import-untyped]

    data = si.system_info
    return yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def to_toml(si: SystemInfo) -> str:
    """Serialize system info data to TOML format."""
    require_toml_feature()
    import tomli_w

    data = si.system_info
    return tomli_w.dumps(data)

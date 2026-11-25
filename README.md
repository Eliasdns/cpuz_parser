# cpuz_parser

[![PyPI version](https://img.shields.io/pypi/v/cpuz_parser.svg)](https://pypi.org/project/cpuz_parser/)
[![Python versions](https://img.shields.io/pypi/pyversions/cpuz_parser.svg)](https://pypi.org/project/cpuz_parser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](https://github.com/Eliasdns/cpuz_parser/blob/main/LICENSE)

Parse [CPU-Z](https://www.cpuid.com/softwares/cpu-z.html) `.txt` hardware reports into structured Python data and human-readable summaries, from the command line or as a Python library.

## Features

- Extracts core system hardware information from CPU-Z `.txt` reports:
  - **Motherboard** (vendor, model)
  - **BIOS** (vendor, version, date)
  - **CPU** (single or multi-socket specifications)
  - **RAM** (total size and per-slot details — either as individual structured dictionaries or merged into single summary strings with duplicate counts)
  - **GPU** (display adapter names)
  - **Operating System** (Windows version)
- **Lightweight base install**: depends only on `click` and supports **Plain Text**, **JSON**, and **XML** out of the box.
- **Optional extras** for **Rich** terminal output, **YAML**, and **TOML** export.
- Supports reading from files or `stdin` (`-`), automatic format deduction from output file extensions, and JSON configuration files to customize RAM slot grouping and normalize calculated RAM frequencies to standard market labels (e.g., `1334` -> `1333`, `2132` -> `2133`).

> **How to generate a CPU-Z TXT report:** open CPU-Z, go to the **About** tab, and click **Save Report (.TXT)**.

---

## Installation

Requires **Python 3.11+**.

### Base installation (`plain`, `json`, `xml`)

```bash
pip install cpuz_parser
```

For CLI-only usage in an isolated environment, you can also use [uv](https://docs.astral.sh/uv/) (`uv tool` / `uvx`) or [pipx](https://pipx.pypa.io/):

```bash
uv tool install "cpuz_parser[all]"
# or run directly without installing
uvx --from "cpuz_parser[all]" cpuz_parser report.txt
# or with pipx
pipx install "cpuz_parser[all]"
```

### Optional dependencies (extras)

| Extra | Packages Installed | Unlocks |
| :--- | :--- | :--- |
| `rich` | `rich`, `rich-click` | Rich panels/tables (terminal and plain-file export), highlighted JSON stdout, styled CLI help |
| `yaml` | `pyyaml` | YAML export (`-f yaml`, `.yaml`/`.yml`, `exporters.to_yaml`) |
| `toml` | `tomli-w` | TOML export (`-f toml`, `.toml`, `exporters.to_toml`) |
| `all` | All of the above | Every output format and Rich UI |

Install one or more extras as needed (quotes avoid shell expansion issues in `zsh`/PowerShell):

```bash
pip install "cpuz_parser[rich]"
pip install "cpuz_parser[yaml,toml]"
pip install "cpuz_parser[all]"
```

---

## CLI Usage

Once installed, invoke `cpuz_parser` (or `python -m cpuz_parser`):

```bash
# Print a report to stdout (uses Rich if installed, otherwise plain text)
cpuz_parser report.txt

# Force plain text or JSON to stdout
cpuz_parser report.txt -f plain
cpuz_parser report.txt -f json

# Export to a file (format is automatically deduced from the extension)
cpuz_parser report.txt -o hardware.json
cpuz_parser report.txt -o hardware.xml
cpuz_parser report.txt -o hardware.yaml   # requires [yaml]
cpuz_parser report.txt -o hardware.toml   # requires [toml]
cpuz_parser report.txt -o hardware.txt    # plain text

# Override deduced format explicitly (Rich panels/tables saved without ANSI codes)
cpuz_parser report.txt -f rich -o hardware_rich.txt
cpuz_parser report.txt -f json -o hardware.out

# Keep each RAM slot as an individual entry instead of combining identical modules
cpuz_parser report.txt --no-auto-combine-slots -f json

# Apply a JSON configuration file
cpuz_parser report.txt -c config.json

# Read report content from stdin
cat report.txt | cpuz_parser - -f json
```

### CLI Options

| Option | Description |
| :--- | :--- |
| `REPORT_FILE` | Path to the CPU-Z `.txt` report, or `-` to read from `stdin` *(required)*. |
| `-c`, `--config FILE` | Path to a JSON configuration file. |
| `--auto-combine-slots` / `--no-auto-combine-slots` | Merge identical RAM slots into counted strings or keep individual slot entries. Overrides `--config` *(default: `True`)*. |
| `-f`, `--format [plain\|rich\|json\|yaml\|toml\|xml]` | Output format (case-insensitive). Defaults to extension mapping for files, or `rich`/`plain` for stdout. |
| `-o`, `--output PATH` | Destination file path, or `-` to print to stdout *(default: `-`)*. |
| `--version` | Show the installed version and exit. |
| `-h`, `--help` | Show CLI help and exit. |

> **Note:** When `-f rich` is used with a file destination (`-o hardware_rich.txt`), Rich panels and tables are written to the file without ANSI color/control sequences so the resulting `.txt` file stays clean and portable.

---

## Configuration File

You can pass a JSON configuration file to the CLI with `-c` / `--config` (see [`config.example.json`](https://github.com/Eliasdns/cpuz_parser/blob/main/config.example.json)):

```json
{
    "auto_combine_slots": true,
    "ram_freqs_single_mul2_to_friendly": {
        "1334": "1333",
        "1778": "1775",
        "2132": "2133",
        "2134": "2133"
    }
}
```

### Supported keys

- **`auto_combine_slots`** (`bool`, optional): controls whether identical RAM modules are merged and counted (see [RAM Slot Output (`auto_combine_slots`)](#ram-slot-output-auto_combine_slots)).
  - **Precedence:** CLI flags (`--auto-combine-slots` / `--no-auto-combine-slots`) > config file > default (`true`).
- **`ram_freqs_single_mul2_to_friendly`** (`dict[str, str]`, optional): adjusts calculated DDR frequencies (`single_rate_mhz * 2`) to standard commercial/market naming conventions.
  - Because CPU-Z reports rounded single-rate clocks such as `667 MHz` (`667 * 2 = 1334`) or `1066 MHz` (`1066 * 2 = 2132`), this map translates them to the conventional market speeds (`1333MHz`, `2133MHz`, etc.).

Both keys are optional and strictly validated; malformed JSON or invalid value types exit with status code `1` and an explanatory error message.

---

## RAM Slot Output (`auto_combine_slots`)

By default (`auto_combine_slots=True`), identical RAM modules are merged into a single string prefixed with their count (`<count>x <type> <bandwidth> <size> <manufacturer>`). Disabling it (`auto_combine_slots=False` or `--no-auto-combine-slots`) preserves every installed slot as an individual structured dictionary.

| Format | `auto_combine_slots=True` *(default)* | `auto_combine_slots=False` |
| :--- | :--- | :--- |
| **Python / JSON / YAML / TOML / XML** | List of counted summary strings | List of structured slot dicts (`type`, `bandwidth`, `size`, `manufacturer`) |
| **Plain Text** | One counted line per unique module (`2x DDR4 2666MHz 8GB Acme Memory`) | One line per installed module without count prefix |
| **Rich** | Single-column table (`Installed RAM Slots`) | 4-column table (`Type`, `Bandwidth`, `Size`, `Manufacturer`) |

### Structured comparison (JSON / `parser.system_info['ram']`)

With `auto_combine_slots=True` *(default)*:

```json
{
  "size": "16GB",
  "slots": [
    "2x DDR4 2666MHz 8GB Acme Memory"
  ]
}
```

With `auto_combine_slots=False` (`--no-auto-combine-slots`):

```json
{
  "size": "16GB",
  "slots": [
    {
      "type": "DDR4",
      "bandwidth": "2666MHz",
      "size": "8GB",
      "manufacturer": "Acme Memory"
    },
    {
      "type": "DDR4",
      "bandwidth": "2666MHz",
      "size": "8GB",
      "manufacturer": "Acme Memory"
    }
  ]
}
```

---

## Python Lib Usage

Import `CpuzTxtParser` directly from `cpuz_parser`:

```python
from cpuz_parser import CpuzTxtParser

# Parse from a file path
parser = CpuzTxtParser('report.txt')

# Structured hardware dictionary (deep copy, safe to mutate without affecting the parser)
info = parser.system_info
print(info['cpu'])
print(info['ram'])

# Human-readable plain-text summary
print(parser)
```

### Parsing from a binary stream with custom options

```python
from cpuz_parser import CpuzTxtParser

freq_map = {'1334': '1333', '2132': '2133'}

with open('report.txt', 'rb') as report_stream:
    parser = CpuzTxtParser(
        report_stream,
        ram_freq_translate=freq_map,
        auto_combine_slots=False,
    )

slots = parser.system_info['ram']['slots']
```

### Using exporters directly

```python
from cpuz_parser import CpuzTxtParser, exporters

parser = CpuzTxtParser('report.txt')

plain_text = exporters.to_plain(parser)
json_str = exporters.to_json(parser, indent=2)
xml_str = exporters.to_xml(parser, root_tag='system_info')

# Optional extras:
# exporters.to_rich(parser)      # requires cpuz_parser[rich]
# exporters.to_yaml(parser)      # requires cpuz_parser[yaml]
# exporters.to_toml(parser)      # requires cpuz_parser[toml]
```

---

## Example Output

### Plain Text (`-f plain` / `str(parser)`)

```text
Motherboard: Acme Corp Z790-Example
BIOS: Acme BIOS v1.0.0 01/01/2025
CPU: Example 8-Core Processor @ 3.60GHz
Memory: 16GB
2x DDR4 2666MHz 8GB Acme Memory
Graphics: Example Graphics Adapter
Operating System: Microsoft Windows 11 (23H2) 64-bit
```

### JSON (`-f json` / `exporters.to_json(parser)`)

```json
{
  "motherboard": {
    "vendor": "Acme Corp",
    "model": "Z790-Example"
  },
  "bios": {
    "vendor": "Acme BIOS",
    "version": "v1.0.0",
    "date": "01/01/2025"
  },
  "cpu": [
    "Example 8-Core Processor @ 3.60GHz"
  ],
  "ram": {
    "size": "16GB",
    "slots": [
      "2x DDR4 2666MHz 8GB Acme Memory"
    ]
  },
  "gpu": [
    "Example Graphics Adapter"
  ],
  "os": [
    "Microsoft Windows 11 (23H2) 64-bit"
  ]
}
```

---

## Links & License

- **Source Code:** [github.com/Eliasdns/cpuz_parser](https://github.com/Eliasdns/cpuz_parser)
- **Issue Tracker:** [github.com/Eliasdns/cpuz_parser/issues](https://github.com/Eliasdns/cpuz_parser/issues)
- **License:** [MIT License](https://github.com/Eliasdns/cpuz_parser/blob/main/LICENSE)

"""Feature toggles detecting optional dependencies and capabilities."""

from __future__ import annotations

from importlib.util import find_spec


# Feature Toggles
FEATURE_RICH: bool = find_spec('rich') is not None and find_spec('rich_click') is not None
FEATURE_YAML: bool = find_spec('yaml') is not None
FEATURE_TOML: bool = find_spec('tomli_w') is not None


def require_rich_feature() -> None:
    """Validate that the Rich feature toggle is active; raise ImportError otherwise."""
    if not FEATURE_RICH:
        raise ImportError(
            "Rich visualization requires 'rich' and 'rich-click'. "
            "Install with: pip install 'cpuz_parser[rich]' (or 'cpuz_parser[all]')"
        )


def require_yaml_feature() -> None:
    """Validate that the YAML feature toggle is active; raise ImportError otherwise."""
    if not FEATURE_YAML:
        raise ImportError(
            "YAML export feature is disabled because 'pyyaml' is not installed. "
            "Install it with: pip install 'cpuz_parser[yaml]' (or 'cpuz_parser[all]')"
        )


def require_toml_feature() -> None:
    """Validate that the TOML feature toggle is active; raise ImportError otherwise."""
    if not FEATURE_TOML:
        raise ImportError(
            "TOML export feature is disabled because 'tomli-w' is not installed. "
            "Install it with: pip install 'cpuz_parser[toml]' (or 'cpuz_parser[all]')"
        )

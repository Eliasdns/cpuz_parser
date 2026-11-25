"""Unit tests for optional feature toggles and requirement guards."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cpuz_parser import features


if TYPE_CHECKING:
    from collections.abc import Callable


pytestmark = pytest.mark.unit


FEATURE_CASES = [
    pytest.param(
        'FEATURE_RICH',
        features.require_rich_feature,
        "Rich visualization requires 'rich'",
        id='rich'
    ),
    pytest.param(
        'FEATURE_YAML',
        features.require_yaml_feature,
        'YAML export feature is disabled',
        id='yaml'
    ),
    pytest.param(
        'FEATURE_TOML',
        features.require_toml_feature,
        'TOML export feature is disabled',
        id='toml'
    ),
]


class TestFeatures:
    """Test feature requirement guard helpers."""

    @pytest.mark.parametrize(('flag_name', 'guard_fn', '_expected_error'), FEATURE_CASES)
    def test_require_feature_succeeds_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flag_name: str,
        guard_fn: Callable[[], None],
        _expected_error: str,
    ) -> None:
        """Verify each require_* guard returns cleanly when its feature flag is enabled."""
        monkeypatch.setattr(features, flag_name, True)
        guard_fn()

    @pytest.mark.parametrize(('flag_name', 'guard_fn', 'expected_error'), FEATURE_CASES)
    def test_require_feature_raises_import_error_when_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        flag_name: str,
        guard_fn: Callable[[], None],
        expected_error: str,
    ) -> None:
        """Verify each require_* guard raises ImportError with install guidance when disabled."""
        monkeypatch.setattr(features, flag_name, False)
        with pytest.raises(ImportError, match=expected_error):
            guard_fn()

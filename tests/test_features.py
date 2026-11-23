"""Unit tests for feature toggles and requirements validation."""

from unittest.mock import patch

import pytest

from cpuz_parser import features


pytestmark = pytest.mark.unit


class TestFeatures:
    """Test feature validation helpers."""

    def test_require_rich_feature_success(self) -> None:
        with patch('cpuz_parser.features.FEATURE_RICH', True):
            features.require_rich_feature()

    def test_require_rich_feature_failure(self) -> None:
        with patch('cpuz_parser.features.FEATURE_RICH', False), pytest.raises(ImportError, match="Rich visualization requires 'rich'"):
            features.require_rich_feature()

    def test_require_yaml_feature_success(self) -> None:
        with patch('cpuz_parser.features.FEATURE_YAML', True):
            features.require_yaml_feature()

    def test_require_yaml_feature_failure(self) -> None:
        with patch('cpuz_parser.features.FEATURE_YAML', False), pytest.raises(ImportError, match="YAML export feature is disabled"):
            features.require_yaml_feature()

    def test_require_toml_feature_success(self) -> None:
        with patch('cpuz_parser.features.FEATURE_TOML', True):
            features.require_toml_feature()

    def test_require_toml_feature_failure(self) -> None:
        with patch('cpuz_parser.features.FEATURE_TOML', False), pytest.raises(ImportError, match="TOML export feature is disabled"):
            features.require_toml_feature()

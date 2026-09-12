from pathlib import Path

import pytest

from routemate.config import Settings
from routemate.errors import ConfigurationError


def test_auto_mode_without_key_uses_offline() -> None:
    settings = Settings.from_env({})

    assert settings.effective_mode == "offline"
    assert settings.dashscope_api_key == ""


def test_auto_mode_with_key_uses_online_without_exposing_key() -> None:
    settings = Settings.from_env({"DASHSCOPE_API_KEY": "example-secret"})

    assert settings.effective_mode == "online"
    assert "example-secret" not in repr(settings)


def test_explicit_online_requires_key() -> None:
    settings = Settings(mode="online", output_dir=Path("runtime_output"))

    with pytest.raises(ConfigurationError, match="DASHSCOPE_API_KEY"):
        settings.validate_online()


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="ROUTEMATE_PORT"):
        Settings.from_env({"ROUTEMATE_PORT": "70000"})


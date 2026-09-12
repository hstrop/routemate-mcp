import json
from pathlib import Path

import pytest

from routemate.errors import ConfigurationError
from routemate.mcp_config import default_server_config, load_server_config


def test_default_config_contains_two_stdio_servers(tmp_path: Path) -> None:
    config = default_server_config(tmp_path)

    assert set(config) == {"weather", "safe_file"}
    assert {item["transport"] for item in config.values()} == {"stdio"}
    assert str(tmp_path.resolve()) in config["safe_file"]["args"]


def test_disabled_remote_config_does_not_require_secrets(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = load_server_config(
        project_root / "servers_config.example.json",
        tmp_path,
        env={"ROUTEMATE_OUTPUT_DIR": str(tmp_path)},
    )

    assert set(config) == {"weather", "safe_file"}
    assert all("enabled" not in item for item in config.values())


def test_enabled_optional_remote_without_env_is_skipped(tmp_path: Path) -> None:
    config_path = tmp_path / "servers.json"
    config_path.write_text(
        json.dumps(
            {
                "local": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [],
                },
                "remote": {
                    "enabled": True,
                    "optional": True,
                    "transport": "sse",
                    "url": "${MISSING_REMOTE_URL}",
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_server_config(config_path, tmp_path, env={})

    assert set(config) == {"local"}


def test_required_remote_without_env_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "servers.json"
    config_path.write_text(
        json.dumps(
            {
                "remote": {
                    "transport": "sse",
                    "url": "${MISSING_REMOTE_URL}",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="MISSING_REMOTE_URL"):
        load_server_config(config_path, tmp_path, env={})


"""MultiServerMCPClient 配置加载与校验。"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ConfigurationError

_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
_TRANSPORTS = {"stdio", "sse", "streamable_http"}


def default_server_config(output_dir: Path) -> dict[str, dict[str, Any]]:
    """构造两台本地 STDIO MCP 服务的默认配置。"""

    return {
        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "routemate.mcp_servers.weather_server"],
        },
        "safe_file": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [
                "-m",
                "routemate.mcp_servers.file_server",
                "--output-dir",
                str(output_dir.expanduser().resolve(strict=False)),
            ],
        },
    }


def _expand_env(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        missing: set[str] = set()

        def replacement(match: re.Match[str]) -> str:
            name = match.group(1)
            replacement_value = env.get(name, "")
            if not replacement_value:
                missing.add(name)
            return replacement_value

        expanded = _ENV_PATTERN.sub(replacement, value)
        if missing:
            names = ", ".join(sorted(missing))
            raise ConfigurationError(f"MCP 配置缺少环境变量：{names}")
        return expanded
    if isinstance(value, list):
        return [_expand_env(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item, env) for key, item in value.items()}
    return value


def _validate_server(name: str, server: dict[str, Any]) -> dict[str, Any]:
    transport = server.get("transport")
    if transport not in _TRANSPORTS:
        raise ConfigurationError(
            f"MCP 服务 {name!r} 的 transport 必须是 {sorted(_TRANSPORTS)} 之一"
        )
    if transport == "stdio":
        if not isinstance(server.get("command"), str) or not server["command"].strip():
            raise ConfigurationError(f"STDIO MCP 服务 {name!r} 缺少 command")
        args = server.get("args", [])
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ConfigurationError(f"STDIO MCP 服务 {name!r} 的 args 必须是字符串数组")
    else:
        url = server.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ConfigurationError(f"远程 MCP 服务 {name!r} 需要 http(s) URL")
    return server


def load_server_config(
    config_path: Path | None,
    output_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """加载配置，并移除仅供 RouteMate 使用的 enabled/optional 字段。"""

    if config_path is None:
        return default_server_config(output_dir)
    try:
        raw = json.loads(config_path.expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"MCP 配置文件不存在：{config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"MCP 配置不是合法 JSON：{exc.msg}") from exc
    if not isinstance(raw, dict) or not raw:
        raise ConfigurationError("MCP 配置根节点必须是非空对象")

    source_env = env if env is not None else os.environ
    result: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise ConfigurationError("每个 MCP 服务都必须是具名对象")
        if item.get("enabled", True) is False:
            continue
        optional = item.get("optional", False) is True
        client_config = {
            key: value
            for key, value in item.items()
            if key not in {"enabled", "optional"}
        }
        try:
            expanded = _expand_env(client_config, source_env)
        except ConfigurationError:
            if optional:
                continue
            raise
        result[name] = _validate_server(name, expanded)
    if not result:
        raise ConfigurationError("MCP 配置没有启用且可用的服务")
    return result


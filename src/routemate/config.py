"""只从环境变量读取的应用配置。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .errors import ConfigurationError

RunMode = Literal["auto", "offline", "online"]


def _parse_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigurationError("ROUTEMATE_PORT 必须是整数") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("ROUTEMATE_PORT 必须位于 1..65535")
    return port


@dataclass(frozen=True, slots=True)
class Settings:
    """运行时配置；密钥字段不会出现在 repr 中。"""

    mode: RunMode = "auto"
    dashscope_api_key: str = field(default="", repr=False)
    qwen_model: str = "qwen-plus"
    output_dir: Path = Path("runtime_output")
    servers_config: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        if env is None:
            try:
                from dotenv import load_dotenv

                load_dotenv()
            except ImportError:
                pass
            source: Mapping[str, str] = os.environ
        else:
            source = env

        mode = source.get("ROUTEMATE_MODE", "auto").strip().lower()
        if mode not in {"auto", "offline", "online"}:
            raise ConfigurationError("ROUTEMATE_MODE 仅支持 auto/offline/online")

        output_dir = Path(source.get("ROUTEMATE_OUTPUT_DIR", "runtime_output"))
        raw_config = source.get("MCP_SERVERS_CONFIG", "").strip()
        servers_config = Path(raw_config) if raw_config else None

        return cls(
            mode=mode,  # type: ignore[arg-type]
            dashscope_api_key=source.get("DASHSCOPE_API_KEY", "").strip(),
            qwen_model=source.get("QWEN_MODEL", "qwen-plus").strip() or "qwen-plus",
            output_dir=output_dir,
            servers_config=servers_config,
            host=source.get("ROUTEMATE_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_parse_port(source.get("ROUTEMATE_PORT", "8000")),
        )

    @property
    def effective_mode(self) -> Literal["offline", "online"]:
        if self.mode == "auto":
            return "online" if self.dashscope_api_key else "offline"
        return self.mode

    def validate_online(self) -> None:
        if self.effective_mode == "online" and not self.dashscope_api_key:
            raise ConfigurationError(
                "在线模式需要 DASHSCOPE_API_KEY；可将 ROUTEMATE_MODE 改为 offline 运行演示"
            )


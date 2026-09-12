"""跨入口复用的轻量数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True, slots=True)
class AgentReply:
    answer: str
    mode: str
    thread_id: str
    tool_calls: tuple[ToolTrace, ...] = field(default_factory=tuple)


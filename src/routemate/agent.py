"""离线演示与在线 LangGraph ReAct Agent 的统一门面。"""

from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings
from .errors import ConfigurationError
from .mcp_config import load_server_config
from .models import AgentReply, ToolTrace
from .offline import OfflineTravelAgent

_THREAD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_SYSTEM_PROMPT = """你是 RouteMate 智能出行助手。
请通过已注册的 MCP 工具完成天气查询、文本保存或路线规划任务。
遵循 ReAct 工作方式：先判断需要哪些工具，观察结果后再决定是否继续调用。
不要编造工具没有返回的数据；天气结果若标记 offline_demo，必须告诉用户它不是实时数据。
写文件时只能提供用户要求的相对路径；不要尝试绕过工具的文件沙箱。
回答保持简洁，并说明关键结果来自哪个工具。
"""


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                pieces.append(item["text"])
        if pieces:
            return "".join(pieces)
    return json.dumps(content, ensure_ascii=False, default=str)


class RouteMateAgent:
    """三个入口共同使用的 Agent 服务。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.mode = self.settings.effective_mode
        self._offline: OfflineTravelAgent | None = None
        self._mcp_client: Any = None
        self._graph: Any = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if self.mode == "offline":
            self._offline = OfflineTravelAgent(self.settings.output_dir)
            self._started = True
            return

        self.settings.validate_online()
        try:
            from langchain_community.chat_models.tongyi import ChatTongyi
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langgraph.checkpoint.memory import InMemorySaver
            from langgraph.prebuilt import create_react_agent
        except ImportError as exc:
            raise ConfigurationError(
                "在线依赖未安装，请执行 pip install -e ."
            ) from exc

        server_config = load_server_config(
            self.settings.servers_config,
            self.settings.output_dir,
        )
        self._mcp_client = MultiServerMCPClient(server_config)
        tools = await self._mcp_client.get_tools()
        if not tools:
            raise ConfigurationError("MCP 客户端未发现任何工具")

        model = ChatTongyi(
            model=self.settings.qwen_model,
            dashscope_api_key=self.settings.dashscope_api_key,
            temperature=0,
        )
        self._graph = create_react_agent(
            model,
            tools,
            prompt=_SYSTEM_PROMPT,
            checkpointer=InMemorySaver(),
        )
        self._started = True

    async def close(self) -> None:
        if self._mcp_client is not None:
            close_method = getattr(self._mcp_client, "aclose", None)
            if close_method is not None:
                await close_method()
        self._started = False

    async def chat(self, message: str, thread_id: str = "default") -> AgentReply:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("message 不能为空")
        if len(cleaned_message) > 4000:
            raise ValueError("message 不能超过 4000 个字符")
        if not _THREAD_ID.fullmatch(thread_id):
            raise ValueError("thread_id 仅允许字母、数字及 _ . : -，长度 1..64")
        if not self._started:
            await self.start()

        if self.mode == "offline":
            assert self._offline is not None
            return await self._offline.chat(cleaned_message, thread_id)

        result = await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": cleaned_message}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = result.get("messages", [])
        last_human_index = max(
            (
                index
                for index, item in enumerate(messages)
                if item.__class__.__name__ == "HumanMessage"
            ),
            default=-1,
        )
        current_messages = messages[last_human_index + 1 :]
        answer = ""
        traces: list[ToolTrace] = []
        call_arguments: dict[str, tuple[str, dict[str, Any]]] = {}
        for item in current_messages:
            for call in getattr(item, "tool_calls", []) or []:
                call_id = str(call.get("id", ""))
                call_arguments[call_id] = (
                    str(call.get("name", "tool")),
                    call.get("args", {}) if isinstance(call.get("args"), dict) else {},
                )
            if item.__class__.__name__ == "ToolMessage":
                call_id = str(getattr(item, "tool_call_id", ""))
                fallback_name = str(getattr(item, "name", "tool") or "tool")
                name, arguments = call_arguments.get(call_id, (fallback_name, {}))
                traces.append(
                    ToolTrace(
                        name=name,
                        arguments=arguments,
                        result=_content_as_text(getattr(item, "content", ""))[:1000],
                    )
                )
            elif item.__class__.__name__ in {"AIMessage", "AIMessageChunk"}:
                candidate = _content_as_text(getattr(item, "content", ""))
                if candidate.strip():
                    answer = candidate
        if not answer:
            answer = "Agent 已完成工具调用，但模型没有返回文本结果。"
        return AgentReply(answer, "online", thread_id, tuple(traces))

    async def __aenter__(self) -> "RouteMateAgent":  # noqa: UP037, PYI034 - keep Python 3.10 compatibility
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

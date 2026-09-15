"""无需模型密钥的确定性演示 Agent。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import AgentReply, ToolTrace
from .sandbox import write_text_safely
from .weather import demo_weather

_CITY_ALIASES = {
    "北京": "北京",
    "上海": "上海",
    "广州": "广州",
    "深圳": "深圳",
    "杭州": "杭州",
    "beijing": "北京",
    "shanghai": "上海",
    "guangzhou": "广州",
    "shenzhen": "深圳",
    "hangzhou": "杭州",
}
_FILE_PATTERN = re.compile(
    r"(?:保存(?:到|为)?|写入|写到|文件(?:名)?(?:为|叫)?)\s*[‘’'\"]?"
    r"([^\s‘’'\"]+\.(?:txt|md|json))",
    flags=re.IGNORECASE,
)
_ROUTE_PATTERN = re.compile(
    r"(?:从|由)?\s*([\u4e00-\u9fff]{2,8})\s*(?:到|去|前往|→|->)\s*"
    r"([\u4e00-\u9fff]{2,8}?)(?=怎么走|路线|导航|$|[？?])"
)


@dataclass(slots=True)
class _ThreadState:
    last_weather_text: str | None = None
    last_city: str | None = None


def _extract_city(message: str) -> str | None:
    lowered = message.casefold()
    if not any(marker in lowered for marker in ("天气", "weather", "温度", "气温")):
        return None
    for alias, canonical in _CITY_ALIASES.items():
        if alias in lowered:
            return canonical
    match = re.search(
        r"(?:查询|查一下|查|看看)?\s*([\u4e00-\u9fff]{2,8})(?:的)?天气", message
    )
    if match:
        return match.group(1)
    return None


def _weather_text(payload: dict) -> str:
    return (
        f"{payload['city']}：{payload['description']}，"
        f"{payload['temperature_c']:g}℃，湿度 {payload['humidity_percent']}%。"
        "（固定演示数据，不代表实时天气）"
    )


class OfflineTravelAgent:
    """通过规则驱动天气→写文件流程，供本地演示和自动化测试使用。"""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self._threads: dict[str, _ThreadState] = {}

    def reset_thread(self, thread_id: str) -> bool:
        """删除一个离线会话，返回该会话是否存在。"""
        return self._threads.pop(thread_id, None) is not None

    async def chat(self, message: str, thread_id: str) -> AgentReply:
        state = self._threads.setdefault(thread_id, _ThreadState())
        traces: list[ToolTrace] = []
        city = _extract_city(message)
        weather_text: str | None = None

        if city is not None or "天气" in message:
            city = city or "北京"
            payload = demo_weather(city)
            weather_text = _weather_text(payload)
            state.last_weather_text = weather_text
            state.last_city = city
            traces.append(
                ToolTrace(
                    name="query_weather_demo",
                    arguments={"city": city},
                    result=weather_text,
                )
            )

        wants_file = any(
            marker in message.casefold()
            for marker in ("保存", "写入", "写到", "save", ".txt", ".md", ".json")
        )
        if wants_file:
            content = weather_text or state.last_weather_text
            if content is None:
                answer = "离线演示中还没有可保存的天气结果，请先查询一个城市的天气。"
                return AgentReply(answer, "offline", thread_id, tuple(traces))
            path_match = _FILE_PATTERN.search(message)
            default_city = state.last_city or "weather"
            relative_path = path_match.group(1) if path_match else f"{default_city}-天气.txt"
            result = write_text_safely(relative_path, content, self.output_dir)
            traces.append(
                ToolTrace(
                    name="write_file_sandbox",
                    arguments={"relative_path": relative_path},
                    result=f"已写入 {result.relative_path}（{result.bytes_written} 字节）",
                )
            )
            answer = f"{content}\n已安全保存到文件沙箱：{result.relative_path}"
            return AgentReply(answer, "offline", thread_id, tuple(traces))

        if weather_text is not None:
            return AgentReply(weather_text, "offline", thread_id, tuple(traces))

        if any(marker in message for marker in ("导航", "路线", "怎么走")):
            route = _ROUTE_PATTERN.search(message)
            if route:
                origin, destination = route.groups()
                result = (
                    f"{origin} → {destination}：离线路线演示约 137 公里，"
                    "驾车约 1 小时 51 分钟；实际路线请以在线地图为准。"
                )
                traces.append(
                    ToolTrace(
                        name="plan_route_demo",
                        arguments={"origin": origin, "destination": destination},
                        result=result,
                    )
                )
                return AgentReply(result, "offline", thread_id, tuple(traces))
            answer = (
                "当前是无密钥离线演示，未连接高德地图 MCP，不能返回实时路线。"
                "请配置并启用 servers_config.example.json 中的一种高德远程传输后切换到在线模式。"
            )
            return AgentReply(answer, "offline", thread_id)

        if any(marker in message for marker in ("行程", "旅行", "出行建议", "带什么", "攻略")):
            answer = (
                "可以按“天气 → 交通 → 行程笔记”来规划：先查询目的地天气，"
                "再确认出发时间和交通方式，最后让我把结果保存为 Markdown 行程单。"
            )
            return AgentReply(answer, "offline", thread_id)

        answer = (
            "RouteMate 当前运行在离线演示模式。你可以输入“查询北京天气”，"
            "或“查询上海天气并保存到 行程/上海天气.md”。"
        )
        return AgentReply(answer, "offline", thread_id)

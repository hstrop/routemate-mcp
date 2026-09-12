import asyncio
from pathlib import Path

from routemate.agent import RouteMateAgent
from routemate.config import Settings


def test_offline_weather_then_save_uses_thread_memory(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = RouteMateAgent(Settings(mode="offline", output_dir=tmp_path))
        await agent.start()
        weather = await agent.chat("查询北京天气", "student-1")
        saved = await agent.chat("保存到 行程/北京天气.md", "student-1")
        await agent.close()

        assert weather.mode == "offline"
        assert "固定演示数据" in weather.answer
        assert weather.tool_calls[0].name == "query_weather_demo"
        assert saved.tool_calls[-1].name == "write_file_sandbox"
        assert (tmp_path / "行程" / "北京天气.md").exists()

    asyncio.run(scenario())


def test_offline_thread_state_is_isolated(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = RouteMateAgent(Settings(mode="offline", output_dir=tmp_path))
        await agent.chat("查询上海天气", "thread-a")
        other = await agent.chat("保存到 other.txt", "thread-b")
        await agent.close()

        assert "还没有可保存" in other.answer
        assert not (tmp_path / "other.txt").exists()

    asyncio.run(scenario())


def test_combined_request_runs_weather_then_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = RouteMateAgent(Settings(mode="offline", output_dir=tmp_path))
        reply = await agent.chat(
            "查询深圳天气并保存到 reports/shenzhen.txt", "combined"
        )
        await agent.close()

        assert [trace.name for trace in reply.tool_calls] == [
            "query_weather_demo",
            "write_file_sandbox",
        ]
        assert (tmp_path / "reports" / "shenzhen.txt").exists()

    asyncio.run(scenario())


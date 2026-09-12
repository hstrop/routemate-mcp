import asyncio
import json
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

from routemate.mcp_config import default_server_config


def _mcp_json(result: list[dict]) -> dict:
    assert result and result[0]["type"] == "text"
    return json.loads(result[0]["text"])


def test_stdio_servers_are_discovered_and_callable(tmp_path: Path) -> None:
    async def scenario() -> None:
        client = MultiServerMCPClient(default_server_config(tmp_path))
        tools = {tool.name: tool for tool in await client.get_tools()}

        assert set(tools) == {"query_weather", "write_file"}
        weather = _mcp_json(
            await tools["query_weather"].ainvoke({"city": "北京"})
        )
        written = _mcp_json(
            await tools["write_file"].ainvoke(
                {"relative_path": "mcp/result.txt", "content": "MCP round trip"}
            )
        )

        assert weather["source"] == "offline_demo"
        assert written["status"] == "written"
        assert (tmp_path / "mcp" / "result.txt").read_text(encoding="utf-8") == (
            "MCP round trip"
        )

    asyncio.run(scenario())

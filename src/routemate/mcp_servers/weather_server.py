"""天气查询 STDIO MCP 服务。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from routemate.weather import query_weather as query_weather_data

mcp = FastMCP("routemate-weather")


@mcp.tool(description="按城市查询天气；未配置 OpenWeather 密钥时返回明确标记的演示数据")
async def query_weather(city: str) -> dict:
    return await query_weather_data(city)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


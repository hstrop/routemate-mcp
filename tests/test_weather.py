import asyncio

import httpx
import pytest

from routemate.weather import query_weather


def test_weather_without_key_is_deterministic_and_labeled() -> None:
    first = asyncio.run(query_weather("北京", api_key=""))
    second = asyncio.run(query_weather("北京", api_key=""))

    assert first == second
    assert first["source"] == "offline_demo"
    assert first["is_realtime"] is False
    assert first["temperature_c"] == 15.0


def test_weather_http_error_does_not_expose_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError) as captured:
                await query_weather(
                    "北京",
                    api_key="never-print-this-key",
                    base_url="https://weather.invalid/current",
                    client=client,
                )
        assert "401" in str(captured.value)
        assert "never-print-this-key" not in str(captured.value)

    asyncio.run(scenario())

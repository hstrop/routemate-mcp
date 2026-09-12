"""天气数据访问：有密钥时调用 OpenWeather，无密钥时返回固定演示数据。"""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEMO_WEATHER: dict[str, tuple[float, str, int]] = {
    "北京": (15.0, "晴", 38),
    "上海": (22.0, "多云", 61),
    "广州": (27.0, "阵雨", 79),
    "深圳": (28.0, "多云", 76),
    "杭州": (23.0, "小雨", 72),
    "beijing": (15.0, "晴", 38),
    "shanghai": (22.0, "多云", 61),
    "guangzhou": (27.0, "阵雨", 79),
    "shenzhen": (28.0, "多云", 76),
    "hangzhou": (23.0, "小雨", 72),
}


def _clean_city(city: str) -> str:
    cleaned = city.strip()
    if not cleaned or len(cleaned) > 80:
        raise ValueError("城市名称长度必须在 1..80 之间")
    if any(ord(character) < 32 for character in cleaned):
        raise ValueError("城市名称不能包含控制字符")
    return cleaned


def demo_weather(city: str) -> dict[str, Any]:
    """返回确定性测试数据，并明确标记不是实时天气。"""

    cleaned = _clean_city(city)
    temperature, description, humidity = _DEMO_WEATHER.get(
        cleaned.casefold(), (20.0, "演示天气", 50)
    )
    return {
        "city": cleaned,
        "temperature_c": temperature,
        "description": description,
        "humidity_percent": humidity,
        "source": "offline_demo",
        "is_realtime": False,
    }


async def query_weather(
    city: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """查询天气；缺少 API key 时自动使用可重复的演示数据。"""

    cleaned = _clean_city(city)
    key = api_key if api_key is not None else os.getenv("OPENWEATHER_API_KEY", "")
    if not key:
        return demo_weather(cleaned)

    endpoint = base_url or os.getenv(
        "OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5/weather"
    )
    params = {
        "q": cleaned,
        "appid": key,
        "units": "metric",
        "lang": "zh_cn",
    }

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=8.0)
    try:
        try:
            response = await http_client.get(endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise RuntimeError(f"天气服务返回 HTTP {status}") from None
        except httpx.RequestError:
            raise RuntimeError("天气服务当前不可达") from None
        except ValueError:
            raise RuntimeError("天气服务返回了无法解析的数据") from None
    finally:
        if owns_client:
            await http_client.aclose()

    weather_items = payload.get("weather") or [{}]
    main = payload.get("main") or {}
    return {
        "city": payload.get("name") or cleaned,
        "temperature_c": main.get("temp"),
        "description": weather_items[0].get("description", "未知"),
        "humidity_percent": main.get("humidity"),
        "source": "openweather",
        "is_realtime": True,
    }

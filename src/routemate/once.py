"""单次调用入口。"""

from __future__ import annotations

import argparse
import asyncio

from .agent import RouteMateAgent
from .config import Settings


async def _invoke(message: str, thread_id: str) -> None:
    async with RouteMateAgent(Settings.from_env()) as agent:
        reply = await agent.chat(message, thread_id)
        print(reply.answer)


def main() -> None:
    parser = argparse.ArgumentParser(description="单次调用 RouteMate")
    parser.add_argument("message", help="发送给 Agent 的问题")
    parser.add_argument("--thread-id", default="once", help="会话标识")
    arguments = parser.parse_args()
    asyncio.run(_invoke(arguments.message, arguments.thread_id))


if __name__ == "__main__":
    main()


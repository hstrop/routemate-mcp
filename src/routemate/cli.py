"""交互式 CLI 入口。"""

from __future__ import annotations

import argparse
import asyncio

from .agent import RouteMateAgent
from .config import Settings


async def _run(thread_id: str) -> None:
    async with RouteMateAgent(Settings.from_env()) as agent:
        print(f"RouteMate 已启动（{agent.mode} 模式），输入 /exit 退出。")
        while True:
            try:
                message = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if message.casefold() in {"/exit", "/quit", "exit", "quit"}:
                break
            if not message:
                continue
            try:
                reply = await agent.chat(message, thread_id)
            except Exception as exc:  # noqa: BLE001 - keep the interactive loop alive on one request failure
                print(f"RouteMate> 请求失败：{exc}")
                continue
            print(f"RouteMate> {reply.answer}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RouteMate 交互式命令行")
    parser.add_argument("--thread-id", default="cli", help="多轮会话标识")
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.thread_id))


if __name__ == "__main__":
    main()

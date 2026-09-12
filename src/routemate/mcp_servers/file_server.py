"""安全文本写入 STDIO MCP 服务。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from routemate.sandbox import write_text_safely

mcp = FastMCP("routemate-safe-file")
_output_dir = Path(os.getenv("ROUTEMATE_OUTPUT_DIR", "runtime_output"))


@mcp.tool(
    description="把 UTF-8 文本写入 RouteMate 文件沙箱；仅接受相对路径和 .txt/.md/.json"
)
def write_file(relative_path: str, content: str) -> dict:
    result = write_text_safely(relative_path, content, _output_dir)
    return {
        "status": "written",
        "relative_path": result.relative_path,
        "bytes_written": result.bytes_written,
    }


def main() -> None:
    global _output_dir
    parser = argparse.ArgumentParser(description="RouteMate safe-file MCP server")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("ROUTEMATE_OUTPUT_DIR", "runtime_output"),
        help="允许写入的唯一根目录",
    )
    arguments = parser.parse_args()
    _output_dir = Path(arguments.output_dir)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


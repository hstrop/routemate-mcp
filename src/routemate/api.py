"""FastAPI HTTP 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import RouteMateAgent
from .config import Settings
from .errors import RouteMateError


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(default="default", min_length=1, max_length=64)


class ToolTraceResponse(BaseModel):
    name: str
    arguments: dict
    result: str


class ChatResponse(BaseModel):
    answer: str
    mode: str
    thread_id: str
    tool_calls: list[ToolTraceResponse]


def create_app(settings: Settings | None = None) -> FastAPI:
    selected_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        agent = RouteMateAgent(selected_settings)
        await agent.start()
        app.state.agent = agent
        try:
            yield
        finally:
            await agent.close()

    application = FastAPI(
        title="RouteMate MCP API",
        version="0.1.0",
        description="通过统一 HTTP 接口调用离线演示或 LangGraph ReAct Agent",
        lifespan=lifespan,
    )

    static_dir = Path(__file__).parent / "static"
    assets_dir = static_dir / "assets"
    application.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @application.get("/", include_in_schema=False)
    async def frontend() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @application.get("/meta")
    async def meta() -> dict[str, object]:
        return {
            "name": "RouteMate",
            "description": "MCP 多工具智能出行助手",
            "mode": selected_settings.effective_mode,
            "tools": ["天气查询", "安全文件写入", "路线规划（在线可选）"],
            "transports": ["STDIO", "SSE（在线配置）"],
        }

    @application.get("/health")
    async def health(request: Request) -> dict[str, object]:
        agent = getattr(request.app.state, "agent", None)
        return {
            "status": "ok",
            "mode": selected_settings.effective_mode,
            "started": bool(agent and agent._started),
        }

    @application.post("/v1/threads/{thread_id}/reset")
    async def reset_thread(thread_id: str, request: Request) -> dict[str, object]:
        try:
            reset = await request.app.state.agent.reset_thread(thread_id)
        except (RouteMateError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not reset:
            raise HTTPException(status_code=409, detail="在线模式请创建新的 thread_id 以开始新会话")
        return {"reset": True, "thread_id": thread_id, "mode": selected_settings.effective_mode}

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        try:
            reply = await request.app.state.agent.chat(
                payload.message, payload.thread_id
            )
        except (RouteMateError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ChatResponse(
            answer=reply.answer,
            mode=reply.mode,
            thread_id=reply.thread_id,
            tool_calls=[
                ToolTraceResponse(
                    name=trace.name,
                    arguments=trace.arguments,
                    result=trace.result,
                )
                for trace in reply.tool_calls
            ],
        )

    return application


app = create_app()


def run() -> None:
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(
        "routemate.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

"""FastAPI HTTP 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
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

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "mode": selected_settings.effective_mode}

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


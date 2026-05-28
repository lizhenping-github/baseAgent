import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI

from .api.middleware import RequestLogMiddleware, exception_handler
from .api.router import init_agent_service, router
from .config import settings
from .service.agent_service import AgentService
from .state.session_manager import SessionManager


def _create_model() -> ChatOpenAI:
    if not settings.LLM_API_KEY:
        print("错误: 未配置 LLM_API_KEY，请在 .env 文件中设置")
        sys.exit(1)
    if not settings.LLM_BASE_URL:
        print("错误: 未配置 LLM_BASE_URL，请在 .env 文件中设置")
        sys.exit(1)
    if not settings.LLM_MODEL_NAME:
        print("错误: 未配置 LLM_MODEL_NAME，请在 .env 文件中设置")
        sys.exit(1)

    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model_name=settings.LLM_MODEL_NAME,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
        streaming=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = SessionManager()
    await session_manager.start()

    model = _create_model()
    service = AgentService(model=model, session_manager=session_manager)
    init_agent_service(service)

    yield

    await session_manager.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Service",
        description="智能体服务 API",
        version="1.0.0",
        lifespan=lifespan,
    )

    origins = [o.strip() for o in settings.AGENT_CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)
    app.add_exception_handler(Exception, exception_handler)
    app.include_router(router)

    return app


app = create_app()


def main():
    import uvicorn
    uvicorn.run(
        "agent.main:app",
        host=settings.AGENT_HOST,
        port=settings.AGENT_PORT,
        reload=settings.ENVIRONMENT == "local",
    )


if __name__ == "__main__":
    main()

import time
import traceback

from starlette.requests import Request
from starlette.responses import JSONResponse


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.time()
        await self.app(scope, receive, send)
        elapsed = time.time() - start
        path = scope.get("path", "")
        method = scope.get("method", "")
        print(f"[{method}] {path} - {elapsed:.3f}s")


async def exception_handler(_request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": f"服务内部错误: {str(exc)}"},
    )

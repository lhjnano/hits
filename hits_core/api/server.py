import asyncio
import threading
from typing import Optional

from fastapi import FastAPI
import uvicorn

from .routes import health, work_log, node, handover


class APIServer:
    def __init__(self, port: int = 8765):
        self.port = port
        self.app: Optional[FastAPI] = None
        self.server: Optional[uvicorn.Server] = None
        self.thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def create_app(self) -> FastAPI:
        app = FastAPI(
            title="HITS API",
            description="Hybrid Intel Trace System API",
            version="0.1.0",
        )
        
        app.include_router(health.router, prefix="/api", tags=["health"])
        app.include_router(work_log.router, prefix="/api", tags=["work-log"])
        app.include_router(node.router, prefix="/api", tags=["node"])
        app.include_router(handover.router, prefix="/api", tags=["handover"])
        
        return app

    def _run_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            loop="asyncio",
        )
        self.server = uvicorn.Server(config)
        self._loop.run_until_complete(self.server.serve())

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        
        self.app = self.create_app()
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server and self._loop:
            self._loop.call_soon_threadsafe(self.server.should_exit)


_api_server: Optional[APIServer] = None


def start_api_server(port: int = 8765) -> APIServer:
    global _api_server
    if _api_server is None:
        _api_server = APIServer(port=port)
        _api_server.start()
    return _api_server


def stop_api_server():
    global _api_server
    if _api_server:
        _api_server.stop()
        _api_server = None

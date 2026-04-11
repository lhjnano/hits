"""FastAPI application factory with security middleware and web UI serving.

Security features:
- Argon2id password hashing (or HMAC-SHA256 fallback)
- JWT access/refresh tokens in HttpOnly cookies
- Content-Security-Policy (CSP) headers
- CORS with strict origin validation
- Rate limiting on authentication endpoints
- Secure response headers (HSTS, X-Frame-Options, etc.)
- Input validation via Pydantic v2
"""

import asyncio
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from .routes import health, work_log, node, handover, auth, knowledge
from ..auth.middleware import SecurityMiddleware


# --- Rate Limiter (simple in-memory) ---

class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None

    def is_limited(self, client_id: str) -> bool:
        """Check if client is rate limited. Returns True if limited."""
        import time
        now = time.time()

        if client_id not in self._requests:
            self._requests[client_id] = []

        # Remove old entries
        self._requests[client_id] = [
            t for t in self._requests[client_id]
            if now - t < self.window_seconds
        ]

        if len(self._requests[client_id]) >= self.max_requests:
            return True

        self._requests[client_id].append(now)
        return False


_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


class APIServer:
    def __init__(self, port: int = 8765, dev_mode: bool = False):
        self.port = port
        self.dev_mode = dev_mode
        self.app: Optional[FastAPI] = None
        self.server = None
        self.thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def create_app(self) -> FastAPI:
        app = FastAPI(
            title="HITS API",
            description="Hybrid Intel Trace System - Secure Web UI",
            version="0.2.0",
        )

        # --- Security Middleware ---
        app.add_middleware(SecurityMiddleware, dev_mode=self.dev_mode)

        # --- CORS ---
        if self.dev_mode:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # --- Rate Limiting for Auth ---
        @app.middleware("http")
        async def rate_limit_auth(request: Request, call_next):
            if request.url.path.startswith("/api/auth/login"):
                client_id = request.client.host if request.client else "unknown"
                if _rate_limiter.is_limited(client_id):
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Too many login attempts. Try again later."},
                    )
            return await call_next(request)

        # --- API Routes ---
        app.include_router(health.router, prefix="/api", tags=["health"])
        app.include_router(auth.router, prefix="/api", tags=["auth"])
        app.include_router(work_log.router, prefix="/api", tags=["work-log"])
        app.include_router(node.router, prefix="/api", tags=["node"])
        app.include_router(handover.router, prefix="/api", tags=["handover"])
        app.include_router(knowledge.router, prefix="/api", tags=["knowledge"])

        # --- Static Files (Web UI) ---
        static_dir = Path(__file__).parent.parent.parent / "hits_web" / "dist"
        if static_dir.exists():
            # Mount static assets
            assets_dir = static_dir / "assets"
            if assets_dir.exists():
                app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

            # SPA fallback: serve index.html for all non-API, non-static routes
            index_html = static_dir / "index.html"

            @app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
            async def spa_fallback(path: str):
                """Serve the SPA index.html for all non-API routes."""
                # Try to serve a specific static file first
                file_path = static_dir / path
                if path and file_path.exists() and file_path.is_file():
                    from fastapi.responses import FileResponse
                    return FileResponse(file_path)
                # Otherwise serve index.html (SPA routing)
                if index_html.exists():
                    return HTMLResponse(content=index_html.read_text(encoding="utf-8"))
                return HTMLResponse(content="<h1>HITS Web UI not built yet. Run: cd hits_web && npm run build</h1>")

        return app

    def _run_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        import uvicorn
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            loop="asyncio",
            log_level="warning" if not self.dev_mode else "info",
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


def start_api_server(port: int = 8765, dev_mode: bool = False) -> APIServer:
    global _api_server
    if _api_server is None:
        _api_server = APIServer(port=port, dev_mode=dev_mode)
        _api_server.start()
    return _api_server


def stop_api_server():
    global _api_server
    if _api_server:
        _api_server.stop()
        _api_server = None

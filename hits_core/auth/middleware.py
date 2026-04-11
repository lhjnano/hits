"""Security middleware for FastAPI.

Applies defense-in-depth headers and protections:
- Content-Security-Policy (CSP): Prevents XSS by restricting resource sources
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking
- Strict-Transport-Security (HSTS): Forces HTTPS
- Referrer-Policy: Limits referrer information leakage
- Permissions-Policy: Restricts browser features
- X-XSS-Protection: Legacy XSS filter
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    def __init__(self, app, dev_mode: bool = False):
        super().__init__(app)
        self.dev_mode = dev_mode

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Content-Security-Policy
        if self.dev_mode:
            # Dev: allow localhost connections for Vite HMR
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' http://localhost:5173; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self' http://localhost:5173 http://localhost:8765; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        else:
            # Production: strict CSP
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"

        if not self.dev_mode:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response

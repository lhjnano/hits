"""Security middleware for FastAPI.

Applies defense-in-depth headers and protections:
- Content-Security-Policy (CSP): Prevents XSS by restricting resource sources
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking
- Strict-Transport-Security (HSTS): Forces HTTPS
- Referrer-Policy: Limits referrer information leakage
- Permissions-Policy: Restricts browser features
- X-XSS-Protection: Legacy XSS filter

NOTE: Implemented as pure ASGI middleware (not BaseHTTPMiddleware) to avoid
the response reconstruction bug where call_next() silently drops Set-Cookie
headers from route handlers (e.g., logout's delete_cookie).
"""


class SecurityMiddleware:
    """Adds security headers to all responses via pure ASGI middleware.

    Unlike BaseHTTPMiddleware, this does not reconstruct the response,
    preserving all cookie modifications from route handlers.
    """

    def __init__(self, app, dev_mode: bool = False):
        self.app = app
        self.dev_mode = dev_mode

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Build CSP string once
        if self.dev_mode:
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

        # Prepare security headers as bytes
        security_headers = [
            (b"content-security-policy", csp.encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"x-xss-protection", b"1; mode=block"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
            (b"cache-control", b"no-store"),
        ]

        if not self.dev_mode:
            security_headers.append((
                b"strict-transport-security",
                b"max-age=63072000; includeSubDomains; preload",
            ))

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(security_headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

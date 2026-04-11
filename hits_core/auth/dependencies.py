"""FastAPI dependencies for authentication.

Usage in routes:
    @router.get("/protected")
    async def protected_route(user: dict = Depends(require_auth)):
        username = user["username"]
        ...

    @router.get("/optional")
    async def optional_route(user: Optional[dict] = Depends(get_current_user)):
        if user:
            # authenticated
        else:
            # anonymous
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from .manager import get_auth_manager


async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and verify user from access token cookie.

    Returns user dict or None if not authenticated.
    """
    token = request.cookies.get("access_token")
    if not token:
        # Also check Authorization header for API clients
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    auth = get_auth_manager()
    return auth.verify_access_token(token)


async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Require authentication. Raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user

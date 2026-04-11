"""Authentication API routes.

Endpoints:
- POST /api/auth/register  → Create user (first user becomes admin)
- POST /api/auth/login     → Authenticate, set HttpOnly cookies
- POST /api/auth/logout    → Clear auth cookies
- POST /api/auth/refresh   → Refresh access token
- GET  /api/auth/me        → Get current user info
- PUT  /api/auth/password  → Change password
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Any, Optional

from hits_core.auth.manager import get_auth_manager
from hits_core.auth.dependencies import get_current_user, require_auth


router = APIRouter()


# --- Request/Response Models ---

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# --- Cookie Settings ---
# Secure cookies: HttpOnly (no JS access), Secure (HTTPS only in prod),
# SameSite=Lax (CSRF protection), path restricted to /api
def _cookie_params(secure: bool = False) -> dict:
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
        "max_age": None,  # session cookie for access
    }


# --- Endpoints ---

@router.post("/auth/register", response_model=APIResponse)
async def register(body: RegisterRequest, request: Request):
    """Register a new user. First user automatically becomes admin."""
    auth = get_auth_manager()

    if auth.has_any_user():
        # Registration requires auth after first user
        user = await get_current_user(request)
        if not user or user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create new users",
            )

    if auth.user_exists(body.username):
        return APIResponse(success=False, error="Username already exists")

    success = auth.create_user(body.username, body.password)
    if not success:
        return APIResponse(success=False, error="Failed to create user")

    return APIResponse(
        success=True,
        data={
            "username": body.username,
            "role": "admin" if not auth.has_any_user() else "user",
            "message": "User created successfully",
        },
    )


@router.post("/auth/login", response_model=APIResponse)
async def login(body: LoginRequest, response: Response):
    """Authenticate and set HttpOnly JWT cookies."""
    auth = get_auth_manager()
    tokens = auth.create_tokens(body.username, body.password)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Set HttpOnly cookies
    # Access token: short-lived (15 min)
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        path="/",
        max_age=900,  # 15 minutes
    )

    # Refresh token: long-lived (7 days)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        path="/api/auth/refresh",  # Only sent to refresh endpoint
        max_age=604800,  # 7 days
    )

    return APIResponse(
        success=True,
        data={
            "username": tokens["username"],
            "role": tokens["role"],
        },
    )


@router.post("/auth/logout", response_model=APIResponse)
async def logout(response: Response):
    """Clear authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    return APIResponse(success=True, data={"message": "Logged out"})


@router.post("/auth/refresh", response_model=APIResponse)
async def refresh_token(request: Request, response: Response):
    """Refresh access token using refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    auth = get_auth_manager()
    new_access = auth.refresh_access_token(refresh_token)

    if not new_access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=900,
    )

    return APIResponse(success=True, data={"message": "Token refreshed"})


@router.get("/auth/me", response_model=APIResponse)
async def get_me(user: dict = Depends(require_auth)):
    """Get current authenticated user info."""
    return APIResponse(success=True, data=user)


@router.put("/auth/password", response_model=APIResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_auth),
):
    """Change password for the authenticated user."""
    auth = get_auth_manager()
    success = auth.change_password(user["username"], body.old_password, body.new_password)

    if not success:
        return APIResponse(success=False, error="Invalid current password")

    return APIResponse(success=True, data={"message": "Password changed"})


@router.get("/auth/status", response_model=APIResponse)
async def auth_status(request: Request):
    """Check if authentication is initialized (has any users)."""
    auth = get_auth_manager()
    user = await get_current_user(request)

    return APIResponse(
        success=True,
        data={
            "initialized": auth.has_any_user(),
            "authenticated": user is not None,
            "username": user.get("username") if user else None,
            "role": user.get("role") if user else None,
        },
    )

"""Authentication and security package for HITS web UI.

Security design:
- Argon2id password hashing (PHC winner, resistant to GPU/ASIC attacks)
- JWT with HttpOnly + Secure + SameSite=Lax cookies (no localStorage)
- Short-lived access tokens (15 min) + long-lived refresh tokens (7 days)
- Rate limiting on auth endpoints
- CSRF protection via SameSite cookies + origin validation
"""

from .manager import AuthManager, get_auth_manager
from .middleware import SecurityMiddleware
from .dependencies import get_current_user, require_auth

__all__ = [
    "AuthManager",
    "get_auth_manager",
    "SecurityMiddleware",
    "get_current_user",
    "require_auth",
]

"""Authentication manager - JWT + Argon2id password hashing.

Security choices:
- Argon2id: Winner of Password Hashing Competition (2015).
  Resistant to GPU, ASIC, and side-channel attacks.
  Parameters: memory=64MB, iterations=3, parallelism=1.
- JWT HS256: Symmetric signing for simplicity in single-server setup.
  Access token: 15 minutes. Refresh token: 7 days.
- HttpOnly cookies: Not accessible to JavaScript (XSS protection).
  Secure flag: Only sent over HTTPS (set False only for localhost dev).
  SameSite=Lax: CSRF protection while allowing top-level navigations.
"""

import json
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Argon2id - fallback to bcrypt if not available
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _HAS_ARGON2 = True
except ImportError:
    import hashlib as _hl

    _HAS_ARGON2 = False

# JWT - use python-jose if available, else pure Python HMAC-based tokens
try:
    from jose import jwt, JWTError

    _HAS_JOSE = True
except ImportError:
    _HAS_JOSE = False


class PasswordHasher:
    """Password hashing with Argon2id (preferred) or HMAC-SHA256 fallback."""

    def __init__(self):
        self._argon2: Optional["PasswordHasher"] = None
        self._pepper: bytes = b""
        self._load_pepper()

        if _HAS_ARGON2:
            self._argon2 = PasswordHasher(
                time_cost=3,        # iterations
                memory_cost=65536,  # 64 MB
                parallelism=1,
                hash_len=32,
                salt_len=16,
            )

    def _load_pepper(self):
        """Load or generate pepper for HMAC fallback."""
        pepper_path = Path.home() / ".hits" / ".pepper"
        pepper_path.parent.mkdir(parents=True, exist_ok=True)

        if pepper_path.exists():
            self._pepper = pepper_path.read_bytes()
        else:
            self._pepper = secrets.token_bytes(32)
            # Restrict permissions to owner only
            pepper_path.write_bytes(self._pepper)
            os.chmod(pepper_path, 0o600)

    def hash_password(self, password: str) -> str:
        """Hash a password. Returns hash string."""
        if self._argon2:
            return self._argon2.hash(password)
        else:
            # Fallback: HMAC-SHA256 with pepper + random salt
            salt = secrets.token_hex(16)
            h = hmac.new(self._pepper, (salt + password).encode(), hashlib.sha256).hexdigest()
            return f"hmac${salt}${h}"

    def verify_password(self, password: str, hash_str: str) -> bool:
        """Verify a password against a hash."""
        if self._argon2 and not hash_str.startswith("hmac$"):
            try:
                self._argon2.verify(hash_str, password)
                return True
            except VerifyMismatchError:
                return False
            except Exception:
                return False
        elif hash_str.startswith("hmac$"):
            parts = hash_str.split("$")
            if len(parts) != 3:
                return False
            salt = parts[1]
            expected = parts[2]
            h = hmac.new(self._pepper, (salt + password).encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(h, expected)
        return False


class TokenManager:
    """JWT token management with HttpOnly cookie support."""

    def __init__(self, secret_key: Optional[str] = None):
        self._secret = secret_key or self._load_or_create_secret()

    def _load_or_create_secret(self) -> str:
        """Load or create a persistent JWT secret key."""
        key_path = Path.home() / ".hits" / ".jwt_secret"
        key_path.parent.mkdir(parents=True, exist_ok=True)

        if key_path.exists():
            return key_path.read_text().strip()
        else:
            secret = secrets.token_urlsafe(48)
            key_path.write_text(secret)
            os.chmod(key_path, 0o600)
            return secret

    def create_access_token(self, username: str, expires_minutes: int = 15) -> str:
        """Create a short-lived access token."""
        payload = {
            "sub": username,
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
            "jti": secrets.token_urlsafe(16),
        }
        if _HAS_JOSE:
            return jwt.encode(payload, self._secret, algorithm="HS256")
        else:
            return self._encode_simple(payload)

    def create_refresh_token(self, username: str, expires_days: int = 7) -> str:
        """Create a long-lived refresh token."""
        payload = {
            "sub": username,
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
            "jti": secrets.token_urlsafe(16),
        }
        if _HAS_JOSE:
            return jwt.encode(payload, self._secret, algorithm="HS256")
        else:
            return self._encode_simple(payload)

    def verify_token(self, token: str, expected_type: str = "access") -> Optional[dict]:
        """Verify and decode a token. Returns payload or None."""
        try:
            if _HAS_JOSE:
                payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            else:
                payload = self._decode_simple(token)

            if payload.get("type") != expected_type:
                return None
            return payload
        except Exception:
            return None

    def _encode_simple(self, payload: dict) -> str:
        """Simple HMAC-based token encoding (fallback without jose)."""
        import base64

        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
        body = base64.urlsafe_b64encode(
            json.dumps(payload, default=str).encode()
        ).decode().rstrip("=")

        signing_input = f"{header}.{body}"
        sig = hmac.new(
            self._secret.encode(), signing_input.encode(), hashlib.sha256
        ).hexdigest()

        return f"{signing_input}.{sig}"

    def _decode_simple(self, token: str) -> dict:
        """Simple HMAC-based token decoding (fallback without jose)."""
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header, body, sig = parts
        signing_input = f"{header}.{body}"
        expected_sig = hmac.new(
            self._secret.encode(), signing_input.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid signature")

        # Decode payload
        padding = 4 - len(body) % 4
        if padding != 4:
            body += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(body))

        # Check expiration
        exp = payload.get("exp")
        if exp:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                raise ValueError("Token expired")

        return payload


class AuthManager:
    """Central authentication manager.

    Manages users, password hashing, and token lifecycle.
    Users are stored in ~/.hits/.auth/users.json with restricted permissions.
    """

    def __init__(self):
        self._hasher = PasswordHasher()
        self._tokens = TokenManager()
        self._users_path = Path.home() / ".hits" / ".auth" / "users.json"
        self._users_path.parent.mkdir(parents=True, exist_ok=True)
        # Restrict auth directory permissions
        os.chmod(self._users_path.parent, 0o700)

    def _load_users(self) -> dict:
        """Load users database."""
        if self._users_path.exists():
            try:
                return json.loads(self._users_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_users(self, users: dict) -> None:
        """Save users database with restricted permissions."""
        self._users_path.write_text(
            json.dumps(users, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(self._users_path, 0o600)

    def create_user(self, username: str, password: str) -> bool:
        """Create a new user. Returns False if username exists."""
        users = self._load_users()
        if username in users:
            return False

        users[username] = {
            "password_hash": self._hasher.hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "role": "admin" if len(users) == 0 else "user",
        }
        self._save_users(users)
        return True

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate a user. Returns access token or None."""
        users = self._load_users()
        user = users.get(username)

        if not user:
            # Constant-time: always hash to prevent timing attacks
            self._hasher.hash_password(secrets.token_urlsafe(16))
            return None

        if not self._hasher.verify_password(password, user["password_hash"]):
            return None

        return self._tokens.create_access_token(username)

    def create_tokens(self, username: str, password: str) -> Optional[dict]:
        """Authenticate and return both access + refresh tokens."""
        users = self._load_users()
        user = users.get(username)

        if not user:
            self._hasher.hash_password(secrets.token_urlsafe(16))
            return None

        if not self._hasher.verify_password(password, user["password_hash"]):
            return None

        return {
            "access_token": self._tokens.create_access_token(username),
            "refresh_token": self._tokens.create_refresh_token(username),
            "username": username,
            "role": user.get("role", "user"),
        }

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Generate a new access token from a valid refresh token."""
        payload = self._tokens.verify_token(refresh_token, expected_type="refresh")
        if not payload:
            return None

        username = payload.get("sub")
        if not username:
            return None

        # Verify user still exists
        users = self._load_users()
        if username not in users:
            return None

        return self._tokens.create_access_token(username)

    def verify_access_token(self, token: str) -> Optional[dict]:
        """Verify an access token. Returns payload with user info."""
        payload = self._tokens.verify_token(token, expected_type="access")
        if not payload:
            return None

        username = payload.get("sub")
        users = self._load_users()
        user = users.get(username)

        if not user:
            return None

        return {
            "username": username,
            "role": user.get("role", "user"),
        }

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change a user's password. Requires current password."""
        users = self._load_users()
        user = users.get(username)

        if not user:
            return False

        if not self._hasher.verify_password(old_password, user["password_hash"]):
            return False

        users[username]["password_hash"] = self._hasher.hash_password(new_password)
        self._save_users(users)
        return True

    def user_exists(self, username: str) -> bool:
        """Check if a user exists."""
        return username in self._load_users()

    def has_any_user(self) -> bool:
        """Check if any user has been created (for initial setup)."""
        return len(self._load_users()) > 0

    def get_user_role(self, username: str) -> Optional[str]:
        """Get user role."""
        users = self._load_users()
        user = users.get(username)
        return user.get("role") if user else None


# Singleton
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create the global AuthManager singleton."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

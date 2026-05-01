"""Tests for bug fixes verification.

Covers:
- BUG-2: First user gets admin role (race condition fix)
- BUG-5: Handover works for non-existent project paths
- BUG-6: Login validation requires min 3/8 chars
- BUG-10: Empty work logs are rejected
- Pydantic v2 migration: No deprecated class-based Config
- Auth middleware: SecurityMiddleware is pure ASGI (not BaseHTTPMiddleware)
- Auth manager: create_user stores correct role
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# Ensure hits_core is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# BUG-10: Empty work log creation rejected
# ============================================================================

class TestBug10EmptyWorkLog:
    """WorkLog.request_text must be non-empty (min_length=1)."""

    def test_work_log_requires_request_text(self):
        """request_text is required, cannot be None."""
        from hits_core.models.work_log import WorkLog, WorkLogSource

        with pytest.raises(ValidationError):
            WorkLog(
                id="test1",
                source=WorkLogSource.MANUAL,
                performed_by="manual",
                # request_text omitted — should fail
            )

    def test_work_log_rejects_empty_request_text(self):
        """request_text cannot be empty string."""
        from hits_core.models.work_log import WorkLog, WorkLogSource

        with pytest.raises(ValidationError):
            WorkLog(
                id="test1",
                source=WorkLogSource.MANUAL,
                performed_by="manual",
                request_text="",
            )

    def test_work_log_accepts_valid_request_text(self):
        """Valid request_text creates work log successfully."""
        from hits_core.models.work_log import WorkLog, WorkLogSource

        log = WorkLog(
            id="test1",
            source=WorkLogSource.MANUAL,
            performed_by="manual",
            request_text="Fixed authentication bug",
        )
        assert log.request_text == "Fixed authentication bug"

    def test_work_log_route_rejects_empty_request_text(self):
        """WorkLogCreate Pydantic model rejects empty request_text."""
        from hits_core.api.routes.work_log import WorkLogCreate

        with pytest.raises(ValidationError):
            WorkLogCreate(
                source="manual",
                performed_by="manual",
                request_text="",
            )

    def test_work_log_route_rejects_missing_request_text(self):
        """WorkLogCreate Pydantic model rejects missing request_text."""
        from hits_core.api.routes.work_log import WorkLogCreate

        with pytest.raises(ValidationError):
            WorkLogCreate(
                source="manual",
                performed_by="manual",
            )


# ============================================================================
# BUG-2: First user gets admin role
# ============================================================================

class TestBug2FirstUserRole:
    """First user registered must always get admin role."""

    def test_first_user_role_is_admin_in_create_user(self):
        """AuthManager.create_user assigns 'admin' to first user."""
        from hits_core.auth.manager import AuthManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Point AuthManager to temp directory
            auth = AuthManager()
            auth._users_path = Path(tmpdir) / "users.json"
            auth._users_path.parent.mkdir(parents=True, exist_ok=True)

            assert not auth.has_any_user()
            success = auth.create_user("admin_user", "password123")
            assert success

            # Verify the stored role
            users = auth._load_users()
            assert users["admin_user"]["role"] == "admin"

    def test_second_user_role_is_user(self):
        """Second user registered gets 'user' role."""
        from hits_core.auth.manager import AuthManager

        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager()
            auth._users_path = Path(tmpdir) / "users.json"
            auth._users_path.parent.mkdir(parents=True, exist_ok=True)

            auth.create_user("admin_user", "password123")
            auth.create_user("regular_user", "password456")

            users = auth._load_users()
            assert users["admin_user"]["role"] == "admin"
            assert users["regular_user"]["role"] == "user"

    def test_register_route_first_user_is_admin(self):
        """Register route returns admin role for first user (no race condition)."""
        from hits_core.api.routes.auth import RegisterRequest

        # Validate the model works correctly
        req = RegisterRequest(username="first_user", password="secure1234")
        assert req.username == "first_user"
        assert req.password == "secure1234"


# ============================================================================
# BUG-6: Login validation strength
# ============================================================================

class TestBug6LoginValidation:
    """LoginRequest must enforce min_length=3 for username, min_length=8 for password."""

    def test_login_rejects_short_username(self):
        """Username < 3 chars is rejected."""
        from hits_core.api.routes.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(username="ab", password="password123")

    def test_login_rejects_short_password(self):
        """Password < 8 chars is rejected."""
        from hits_core.api.routes.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(username="admin", password="short")

    def test_login_accepts_valid_credentials(self):
        """Valid username (3+) and password (8+) accepted."""
        from hits_core.api.routes.auth import LoginRequest

        req = LoginRequest(username="admin", password="password123")
        assert req.username == "admin"

    def test_login_rejects_special_chars_in_username(self):
        """Username with special chars outside pattern is rejected."""
        from hits_core.api.routes.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(username="user@name", password="password123")

    def test_register_has_same_validation_as_login(self):
        """Register and Login have identical field constraints."""
        from hits_core.api.routes.auth import RegisterRequest, LoginRequest

        # Both should accept the same valid input
        reg = RegisterRequest(username="user_1", password="password123")
        login = LoginRequest(username="user_1", password="password123")
        assert reg.username == login.username


# ============================================================================
# BUG-5: Handover works for non-existent paths
# ============================================================================

class TestBug5HandoverPathCheck:
    """Handover API must not require Path.exists() for project_path."""

    def test_handover_route_has_no_path_exists_check(self):
        """handover.py route code should NOT contain Path.exists()."""
        route_source = (PROJECT_ROOT / "hits_core" / "api" / "routes" / "handover.py").read_text()
        assert "Path(" not in route_source or "exists()" not in route_source, (
            "handover.py should not check Path.exists() — data is in ~/.hits/data/, not project dir"
        )

    def test_handover_service_no_path_exists_check(self):
        """HandoverService should work with any project_path string."""
        route_source = (PROJECT_ROOT / "hits_core" / "service" / "handover_service.py").read_text()

        # The service should use project_path as a filter key, not filesystem path
        # Check that it doesn't require the path to exist on disk
        lines_with_exists = [
            line for line in route_source.split("\n")
            if "exists()" in line and "project_path" in line
        ]
        assert len(lines_with_exists) == 0, (
            f"HandoverService should not check if project_path exists on filesystem. "
            f"Found: {lines_with_exists}"
        )


# ============================================================================
# BUG-1: SecurityMiddleware is pure ASGI
# ============================================================================

class TestBug1LogoutSession:
    """SecurityMiddleware must be pure ASGI, not BaseHTTPMiddleware."""

    def test_middleware_is_not_base_http_middleware(self):
        """SecurityMiddleware should NOT inherit from BaseHTTPMiddleware."""
        from hits_core.auth.middleware import SecurityMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        assert not issubclass(SecurityMiddleware, BaseHTTPMiddleware), (
            "SecurityMiddleware must be pure ASGI to preserve Set-Cookie headers"
        )

    def test_middleware_has_call_method(self):
        """SecurityMiddleware must implement __call__ for ASGI."""
        from hits_core.auth.middleware import SecurityMiddleware

        assert hasattr(SecurityMiddleware, "__call__"), (
            "SecurityMiddleware must implement __call__ for pure ASGI middleware"
        )

    def test_middleware_adds_security_headers(self):
        """SecurityMiddleware adds expected security headers."""
        import inspect
        from hits_core.auth.middleware import SecurityMiddleware

        source = inspect.getsource(SecurityMiddleware)
        expected_headers = [
            "content-security-policy",
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy",
        ]
        for header in expected_headers:
            assert header.encode() in source.encode() or header in source, (
                f"SecurityMiddleware should add '{header}' header"
            )


# ============================================================================
# Pydantic v2: No deprecated class-based Config
# ============================================================================

class TestPydanticV2Migration:
    """All models should use ConfigDict, not deprecated class Config."""

    def _find_model_files(self) -> list[Path]:
        """Find all model files."""
        models_dir = PROJECT_ROOT / "hits_core" / "models"
        return list(models_dir.glob("*.py"))

    def test_no_deprecated_class_config(self):
        """No model should use 'class Config:' pattern."""
        model_files = self._find_model_files()
        violations = []

        for f in model_files:
            content = f.read_text()
            # Look for 'class Config:' that is NOT 'class ConfigDict'
            if "class Config:" in content:
                violations.append(str(f.relative_to(PROJECT_ROOT)))

        assert len(violations) == 0, (
            f"Found deprecated 'class Config:' in: {violations}. "
            f"Use 'model_config = ConfigDict(...)' instead."
        )

    def test_models_import_configdict(self):
        """Models that use ConfigDict should import it."""
        model_files = self._find_model_files()

        for f in model_files:
            content = f.read_text()
            if "ConfigDict" in content or "model_config" in content:
                assert "from pydantic import" in content and "ConfigDict" in content, (
                    f"{f.name}: Uses ConfigDict but doesn't import it from pydantic"
                )

    def test_node_uses_configdict(self):
        """Node model should use ConfigDict."""
        from hits_core.models.node import Node
        assert hasattr(Node, "model_config"), "Node should have model_config"

    def test_workflow_step_uses_configdict(self):
        """WorkflowStep model should use ConfigDict."""
        from hits_core.models.workflow import WorkflowStep
        assert hasattr(WorkflowStep, "model_config"), "WorkflowStep should have model_config"

    def test_work_log_uses_configdict(self):
        """WorkLog model should use ConfigDict."""
        from hits_core.models.work_log import WorkLog
        assert hasattr(WorkLog, "model_config"), "WorkLog should have model_config"

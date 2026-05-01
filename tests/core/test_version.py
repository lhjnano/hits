"""Test version consistency across all packages.

Validates that __init__.py, pyproject.toml, package.json, and MCP server
all report the same version, and that MCP server imports it dynamically.
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure hits_core is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _read_pyproject_version() -> str:
    """Extract version from pyproject.toml."""
    content = (PROJECT_ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match, "version field not found in pyproject.toml"
    return match.group(1)


def _read_package_json_version() -> str:
    """Extract version from package.json."""
    content = json.loads((PROJECT_ROOT / "package.json").read_text())
    return content["version"]


class TestVersionConsistency:
    """All version sources must agree on a single version number."""

    def test_init_version_matches_pyproject(self):
        """hits_core.__version__ must match pyproject.toml version."""
        from hits_core import __version__

        pyproject_version = _read_pyproject_version()
        assert __version__ == pyproject_version, (
            f"__init__.py={__version__} != pyproject.toml={pyproject_version}"
        )

    def test_init_version_matches_package_json(self):
        """hits_core.__version__ must match package.json version."""
        from hits_core import __version__

        npm_version = _read_package_json_version()
        assert __version__ == npm_version, (
            f"__init__.py={__version__} != package.json={npm_version}"
        )

    def test_mcp_server_uses_dynamic_version(self):
        """MCP server SERVER_INFO should import __version__, not hardcode it."""
        from hits_core.mcp.server import HITSMCPServer

        server = HITSMCPServer()
        from hits_core import __version__

        assert server.SERVER_INFO["version"] == __version__, (
            f"MCP server version={server.SERVER_INFO['version']} != __version__={__version__}"
        )

    def test_mcp_server_no_hardcoded_version(self):
        """Verify the MCP server source file does not contain hardcoded version literals."""
        server_source = (PROJECT_ROOT / "hits_core" / "mcp" / "server.py").read_text()

        # Look for patterns like "0.1.0" or "1.0.2" as string literals
        stale_versions = re.findall(r'["\'](\d+\.\d+\.\d+)["\']', server_source)
        from hits_core import __version__

        for found in stale_versions:
            assert found == __version__, (
                f"Found hardcoded version '{found}' in server.py that doesn't match __version__ '{__version__}'. "
                "Use __version__ import instead."
            )

    def test_version_is_semver(self):
        """Version must follow semver (MAJOR.MINOR.PATCH)."""
        from hits_core import __version__

        parts = __version__.split(".")
        assert len(parts) == 3, f"Version '{__version__}' is not semver (expected 3 parts)"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' is not numeric"

    def test_pyproject_development_status_is_beta_or_higher(self):
        """Development Status should be Beta (4) or higher, not Alpha (3)."""
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "Development Status :: 4 - Beta" in content or "Development Status :: 5" in content, (
            "Development Status should be Beta (4) or higher. Currently still Alpha."
        )

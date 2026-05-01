"""Tests for LLM Client implementation.

Covers:
- MockLLMProvider: always available, returns placeholder
- OpenAIProvider: auto-detection, HTTP payload construction
- AnthropicProvider: auto-detection, HTTP payload construction
- create_provider: factory auto-detection logic
- LLMClient: all public methods + fallback behavior + usage tracking
- New methods: smart_compress, extract_insights, get_usage_stats
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hits_core.ai.llm_client import (
    LLMClient,
    LLMProvider,
    MockLLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    create_provider,
    LLMUsage,
)


# ============================================================================
# MockLLMProvider
# ============================================================================

class TestMockLLMProvider:

    @pytest.mark.asyncio
    async def test_generate_returns_mock_response(self):
        provider = MockLLMProvider()
        result = await provider.generate("test prompt", max_tokens=100)
        assert "[Mock Response]" in result
        assert "test prompt" in result

    @pytest.mark.asyncio
    async def test_generate_truncates_long_prompt(self):
        provider = MockLLMProvider()
        result = await provider.generate("x" * 200, max_tokens=100)
        assert len(result) < 100  # mock response is short

    def test_is_always_available(self):
        assert MockLLMProvider().is_available() is True


# ============================================================================
# OpenAIProvider
# ============================================================================

class TestOpenAIProvider:

    def test_reads_api_key_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}):
            provider = OpenAIProvider()
            assert provider.api_key == "sk-test-123"
            assert provider.is_available() is True

    def test_reads_api_key_from_hits_env(self):
        with patch.dict(os.environ, {"HITS_LLM_API_KEY": "sk-hits-456"}, clear=False):
            # HITS_LLM_API_KEY takes priority
            provider = OpenAIProvider()
            assert provider.is_available() is True

    def test_explicit_api_key_overrides_env(self):
        provider = OpenAIProvider(api_key="sk-explicit")
        assert provider.api_key == "sk-explicit"

    def test_not_available_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove all possible env vars
            for key in ["OPENAI_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            provider = OpenAIProvider()
            assert provider.is_available() is False

    def test_default_model(self):
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.model == "gpt-4o-mini"

    def test_custom_model(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.model == "gpt-4o"

    def test_custom_base_url(self):
        provider = OpenAIProvider(api_key="sk-test", base_url="http://localhost:8080/v1")
        assert provider.base_url == "http://localhost:8080/v1"

    @pytest.mark.asyncio
    async def test_generate_raises_without_key(self):
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.api_key = None
        provider.model = "gpt-4o-mini"
        provider.base_url = OpenAIProvider.API_BASE

        with pytest.raises(RuntimeError, match="not configured"):
            await provider.generate("test")


# ============================================================================
# AnthropicProvider
# ============================================================================

class TestAnthropicProvider:

    def test_reads_api_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}):
            provider = AnthropicProvider()
            assert provider.api_key == "sk-ant-123"
            assert provider.is_available() is True

    def test_not_available_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            for key in ["ANTHROPIC_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            provider = AnthropicProvider()
            assert provider.is_available() is False

    def test_default_model(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert "claude" in provider.model.lower()

    @pytest.mark.asyncio
    async def test_generate_raises_without_key(self):
        provider = AnthropicProvider.__new__(AnthropicProvider)
        provider.api_key = None
        provider.model = "claude-3-haiku"
        provider.base_url = AnthropicProvider.API_BASE

        with pytest.raises(RuntimeError, match="not configured"):
            await provider.generate("test")


# ============================================================================
# create_provider factory
# ============================================================================

class TestCreateProvider:

    def test_explicit_mock(self):
        provider = create_provider("mock")
        assert isinstance(provider, MockLLMProvider)

    def test_explicit_openai_with_key(self):
        provider = create_provider("openai", api_key="sk-test")
        assert isinstance(provider, OpenAIProvider)

    def test_explicit_openai_without_key_falls_back(self):
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            provider = create_provider("openai")
            assert isinstance(provider, MockLLMProvider)

    def test_explicit_anthropic_with_key(self):
        provider = create_provider("anthropic", api_key="sk-ant-test")
        assert isinstance(provider, AnthropicProvider)

    def test_auto_detect_openai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            provider = create_provider("auto")
            assert isinstance(provider, OpenAIProvider)

    def test_auto_detect_anthropic(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            provider = create_provider("auto")
            assert isinstance(provider, AnthropicProvider)

    def test_auto_detect_no_key_falls_back(self):
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            provider = create_provider("auto")
            assert isinstance(provider, MockLLMProvider)

    def test_env_var_provider_name(self):
        with patch.dict(os.environ, {"HITS_LLM_PROVIDER": "mock"}):
            provider = create_provider()
            assert isinstance(provider, MockLLMProvider)


# ============================================================================
# LLMClient — core methods
# ============================================================================

class TestLLMClientCore:

    @pytest.mark.asyncio
    async def test_analyze_node_with_mock(self):
        client = LLMClient(provider="mock")
        result = await client.analyze_node("test node data")
        assert "[Mock Response]" in result

    @pytest.mark.asyncio
    async def test_suggest_children_with_mock(self):
        client = LLMClient(provider="mock")
        result = await client.suggest_children("test node")
        # Mock returns single line, so we get 1 suggestion
        assert isinstance(result, list)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_generate_handover_with_mock(self):
        client = LLMClient(provider="mock")
        result = await client.generate_handover_summary("tree data")
        assert "[Mock Response]" in result

    def test_default_creates_auto_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            client = LLMClient()
            assert isinstance(client.provider, MockLLMProvider)

    def test_explicit_provider_instance(self):
        mock = MockLLMProvider()
        client = LLMClient(provider=mock)
        assert client.provider is mock

    def test_is_live_false_for_mock(self):
        client = LLMClient(provider="mock")
        assert client.is_live() is False

    def test_is_live_true_for_real_provider(self):
        client = LLMClient(provider=OpenAIProvider(api_key="sk-test"))
        assert client.is_live() is True


# ============================================================================
# LLMClient — new methods
# ============================================================================

class TestLLMClientNewMethods:

    @pytest.mark.asyncio
    async def test_smart_compress_with_mock(self):
        client = LLMClient(provider="mock")
        result = await client.smart_compress("long checkpoint text" * 50)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_extract_insights_with_mock(self):
        client = LLMClient(provider="mock")
        result = await client.extract_insights([
            "Fixed authentication bug",
            "Deployed v2.1 to production",
        ])
        assert isinstance(result, dict)
        assert "progress_summary" in result
        assert "key_decisions" in result

    def test_get_usage_stats(self):
        client = LLMClient(provider="mock")
        stats = client.get_usage_stats()
        assert stats["provider"] == "MockLLMProvider"
        assert stats["is_live"] is False
        assert stats["total_requests"] == 0


# ============================================================================
# LLMClient — fallback behavior
# ============================================================================

class TestLLMClientFallback:

    @pytest.mark.asyncio
    async def test_fallback_on_provider_error(self):
        """When real provider fails, LLMClient falls back to mock."""
        failing_provider = AsyncMock(spec=LLMProvider)
        failing_provider.generate = AsyncMock(side_effect=RuntimeError("API error"))
        failing_provider.is_available = MagicMock(return_value=True)

        client = LLMClient(provider=failing_provider)
        result = await client.analyze_node("test data")

        # Should get mock fallback, not exception
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_error_count_tracked(self):
        failing_provider = AsyncMock(spec=LLMProvider)
        failing_provider.generate = AsyncMock(side_effect=RuntimeError("API error"))
        failing_provider.is_available = MagicMock(return_value=True)

        client = LLMClient(provider=failing_provider)
        await client.analyze_node("test")
        await client.analyze_node("test")

        stats = client.get_usage_stats()
        assert stats["total_errors"] == 2

    @pytest.mark.asyncio
    async def test_request_count_tracked(self):
        client = LLMClient(provider="mock")
        await client.analyze_node("test")
        await client.suggest_children("test")

        stats = client.get_usage_stats()
        assert stats["total_requests"] == 2


# ============================================================================
# LLMUsage dataclass
# ============================================================================

class TestLLMUsage:

    def test_default_values(self):
        usage = LLMUsage()
        assert usage.total_requests == 0
        assert usage.total_tokens_in == 0
        assert usage.total_tokens_out == 0
        assert usage.total_errors == 0
        assert usage.last_model == ""

    def test_custom_values(self):
        usage = LLMUsage(total_requests=5, total_errors=1)
        assert usage.total_requests == 5
        assert usage.total_errors == 1


# ============================================================================
# Backward compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Ensure existing code patterns still work."""

    def test_old_import_pattern(self):
        """from hits_core.ai import LLMClient should still work."""
        from hits_core.ai import LLMClient
        assert LLMClient is not None

    def test_old_construction_with_none(self):
        """LLMClient(provider=None) should auto-detect."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            client = LLMClient(provider=None)
            assert isinstance(client.provider, MockLLMProvider)

    def test_old_construction_no_args(self):
        """LLMClient() should auto-detect."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HITS_LLM_API_KEY"]:
                os.environ.pop(key, None)
            client = LLMClient()
            assert isinstance(client.provider, MockLLMProvider)

    def test_old_method_signatures(self):
        """analyze_node, suggest_children, generate_handover_summary exist."""
        client = LLMClient()
        assert hasattr(client, "analyze_node")
        assert hasattr(client, "suggest_children")
        assert hasattr(client, "generate_handover_summary")
        assert hasattr(client, "total_tokens_used")  # old attr via usage

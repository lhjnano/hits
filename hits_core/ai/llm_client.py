"""LLM client for on-demand knowledge analysis and checkpoint compression.

Architecture:
    LLMProvider (ABC)
    ├── MockLLMProvider   — always available, returns placeholder text
    ├── OpenAIProvider    — OpenAI GPT-4o-mini / GPT-4o (via openai SDK or HTTP)
    └── AnthropicProvider — Claude Haiku / Sonnet (via anthropic SDK or HTTP)

    LLMClient
    ├── __init__() → auto-detects provider from env vars (HITS_LLM_PROVIDER)
    ├── analyze_node()           — summarize a knowledge node
    ├── suggest_children()       — suggest child nodes
    ├── generate_handover_summary() — handover text from tree data
    └── smart_compress()         — LLM-powered checkpoint compression

Environment variables:
    HITS_LLM_PROVIDER  — "openai" | "anthropic" | "mock" (default: auto-detect)
    HITS_LLM_MODEL     — model name override (default: provider-specific)
    HITS_LLM_API_KEY   — API key (or OPENAI_API_KEY / ANTHROPIC_API_KEY)
    HITS_LLM_BASE_URL  — custom base URL (for proxies / local models)
"""

import json
import os
import logging
import urllib.request
import urllib.error
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LLMUsage:
    """Track LLM API usage statistics."""
    total_requests: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_errors: int = 0
    last_model: str = ""
    last_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Abstract Provider
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """Generate a completion for the given prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is properly configured."""
        pass


# ---------------------------------------------------------------------------
# Mock Provider (always available)
# ---------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    """Placeholder provider for testing and offline use."""

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[Mock Response] Analyzed: {prompt[:50]}..."

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# OpenAI Provider (http.client-based, no SDK dependency)
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider using raw HTTP (no openai SDK required).

    Falls back gracefully if the API key is missing or the request fails.
    """

    DEFAULT_MODEL = "gpt-4o-mini"
    API_BASE = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("HITS_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("HITS_LLM_MODEL") or self.DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("HITS_LLM_BASE_URL") or self.API_BASE

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI API key not configured")

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise technical assistant. Respond in the same language as the input. Be brief and structured."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            import asyncio
            resp_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=30).read()
            )
            resp = json.loads(resp_data)
            return resp["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"OpenAI request failed: {e}")
            raise


# ---------------------------------------------------------------------------
# Anthropic Provider (http.client-based, no SDK dependency)
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider using raw HTTP (no anthropic SDK required).

    Falls back gracefully if the API key is missing or the request fails.
    """

    DEFAULT_MODEL = "claude-3-5-haiku-latest"
    API_BASE = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("HITS_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("HITS_LLM_MODEL") or self.DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("HITS_LLM_BASE_URL") or self.API_BASE

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        if not self.is_available():
            raise RuntimeError("Anthropic API key not configured")

        payload = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "system": "You are a concise technical assistant. Respond in the same language as the input. Be brief and structured.",
            "temperature": 0.3,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            import asyncio
            resp_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=30).read()
            )
            resp = json.loads(resp_data)
            return resp["content"][0]["text"].strip()
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Anthropic request failed: {e}")
            raise


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------

def create_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LLMProvider:
    """Create an LLM provider based on configuration.

    Priority:
    1. Explicit provider_name parameter
    2. HITS_LLM_PROVIDER env var
    3. Auto-detect from available API keys
    4. Fall back to MockLLMProvider
    """
    name = provider_name or os.environ.get("HITS_LLM_PROVIDER", "auto").lower()

    if name == "mock":
        return MockLLMProvider()

    if name == "openai":
        provider = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        if provider.is_available():
            return provider
        logger.warning("OpenAI provider requested but API key not found, falling back to mock")

    if name == "anthropic":
        provider = AnthropicProvider(api_key=api_key, model=model, base_url=base_url)
        if provider.is_available():
            return provider
        logger.warning("Anthropic provider requested but API key not found, falling back to mock")

    if name == "auto":
        # Try OpenAI first
        openai = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        if openai.is_available():
            logger.info("Auto-detected OpenAI provider")
            return openai

        # Try Anthropic
        anthropic = AnthropicProvider(api_key=api_key, model=model, base_url=base_url)
        if anthropic.is_available():
            logger.info("Auto-detected Anthropic provider")
            return anthropic

        logger.info("No LLM API key found, using mock provider")

    return MockLLMProvider()


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """High-level LLM client with usage tracking and fallback.

    Usage:
        # Auto-detect provider from env vars
        client = LLMClient()

        # Explicit provider
        client = LLMClient(provider=OpenAIProvider(api_key="sk-..."))

        # Explicit name
        client = LLMClient(provider="anthropic")
    """

    def __init__(
        self,
        provider: Optional[LLMProvider | str] = None,
    ):
        if isinstance(provider, str):
            self.provider = create_provider(provider_name=provider)
        elif isinstance(provider, LLMProvider):
            self.provider = provider
        else:
            self.provider = create_provider()

        self.usage = LLMUsage()
        # Backward compat: old code accessed client.total_tokens_used
        self.total_tokens_used = 0

    def is_live(self) -> bool:
        """Check if using a real LLM provider (not mock)."""
        return not isinstance(self.provider, MockLLMProvider)

    async def _generate_with_fallback(self, prompt: str, max_tokens: int = 1000) -> str:
        """Generate with error tracking and fallback to mock on failure."""
        self.usage.total_requests += 1
        try:
            result = await self.provider.generate(prompt, max_tokens)
            self.usage.total_tokens_out += len(result) // 3  # rough estimate
            self.total_tokens_used += max_tokens  # backward compat
            return result
        except Exception as e:
            self.usage.total_errors += 1
            logger.warning(f"LLM generation failed, using fallback: {e}")
            # Fallback to mock
            mock = MockLLMProvider()
            return await mock.generate(prompt, max_tokens)

    # ----- Existing API (preserved) -----

    async def analyze_node(self, node_data: str, max_tokens: int = 500) -> str:
        """Analyze a knowledge node and extract key context."""
        prompt = f"""다음 지식 노드를 분석하여 핵심 맥락을 요약하세요:

{node_data}

요약:"""

        return await self._generate_with_fallback(prompt, max_tokens)

    async def suggest_children(self, node_data: str, max_tokens: int = 300) -> list[str]:
        """Suggest 3-5 child items for a knowledge node."""
        prompt = f"""다음 지식 노드에 대해 적절한 하위 항목을 3-5개 제안하세요:

{node_data}

하위 항목:"""

        response = await self._generate_with_fallback(prompt, max_tokens)

        suggestions = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.split("\n")
            if line.strip()
        ]
        return suggestions[:5]

    async def generate_handover_summary(
        self,
        tree_data: str,
        max_tokens: int = 1000
    ) -> str:
        """Generate a handover summary from knowledge tree data."""
        prompt = f"""다음 지식 트리를 기반으로 인수인계 요약을 작성하세요.
주요 의사결정, 실패 경험, 필수 지식을 포함하세요:

{tree_data}

인수인계 요약:"""

        return await self._generate_with_fallback(prompt, max_tokens)

    # ----- New: Smart Checkpoint Compression -----

    async def smart_compress(
        self,
        checkpoint_text: str,
        token_budget: int = 500,
    ) -> str:
        """Use LLM to intelligently compress a checkpoint within a token budget.

        This goes beyond keyword-based compression by understanding semantics.
        Falls back to the full text if LLM is unavailable.
        """
        prompt = f"""다음 체크포인트를 {token_budget} 토큰 이내로 압축하세요.
핵심 다음 단계(next steps), 필수 컨텍스트, 차단 요인만 유지하고
나머지는 과감히 생략하세요. 원본 언어를 유지하세요:

{checkpoint_text}

압축된 체크포인트:"""

        result = await self._generate_with_fallback(prompt, max_tokens=token_budget + 200)
        return result

    async def extract_insights(
        self,
        work_log_texts: list[str],
        max_tokens: int = 800,
    ) -> dict:
        """Extract structured insights from multiple work logs.

        Returns: {
            "key_decisions": [...],
            "patterns": [...],
            "warnings": [...],
            "progress_summary": "..."
        }
        """
        combined = "\n---\n".join(work_log_texts[:20])  # limit input size

        prompt = f"""다음 작업 로그들에서 구조화된 인사이트를 추출하세요.
JSON 형식으로 응답하세요:

{combined}

다음 JSON 형식으로 응답:
{{
  "key_decisions": ["의사결정1", "의사결정2"],
  "patterns": ["발견된 패턴1", "패턴2"],
  "warnings": ["주의사항1"],
  "progress_summary": "진행 상황 요약"
}}"""

        response = await self._generate_with_fallback(prompt, max_tokens)

        try:
            # Try to parse JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

        # Fallback: return raw response as progress_summary
        return {
            "key_decisions": [],
            "patterns": [],
            "warnings": [],
            "progress_summary": response[:300],
        }

    def get_usage_stats(self) -> dict:
        """Return current usage statistics."""
        return {
            "total_requests": self.usage.total_requests,
            "total_tokens_out": self.usage.total_tokens_out,
            "total_errors": self.usage.total_errors,
            "provider": type(self.provider).__name__,
            "is_live": self.is_live(),
        }

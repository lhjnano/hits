"""LLM client for on-demand knowledge analysis."""

from typing import Optional
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        pass


class MockLLMProvider(LLMProvider):
    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        return f"[Mock Response] Analyzed: {prompt[:50]}..."


class LLMClient:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or MockLLMProvider()
        self.total_tokens_used = 0
    
    async def analyze_node(self, node_data: str, max_tokens: int = 500) -> str:
        prompt = f"""다음 지식 노드를 분석하여 핵심 맥락을 요약하세요:

{node_data}

요약:"""
        
        response = await self.provider.generate(prompt, max_tokens)
        self.total_tokens_used += max_tokens
        return response
    
    async def suggest_children(self, node_data: str, max_tokens: int = 300) -> list[str]:
        prompt = f"""다음 지식 노드에 대해 적절한 하위 항목을 3-5개 제안하세요:

{node_data}

하위 항목:"""
        
        response = await self.provider.generate(prompt, max_tokens)
        self.total_tokens_used += max_tokens
        
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
        prompt = f"""다음 지식 트리를 기반으로 인수인계 요약을 작성하세요.
주요 의사결정, 실패 경험, 필수 지식을 포함하세요:

{tree_data}

인수인계 요약:"""
        
        response = await self.provider.generate(prompt, max_tokens)
        self.total_tokens_used += max_tokens
        return response

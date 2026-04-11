"""Semantic compression for token-efficient knowledge storage."""

from typing import Optional
from ..models.node import Node


class SemanticCompressor:
    KEYWORD_MAP = {
        "따라서": "→",
        "그래서": "→",
        "그러므로": "→",
        "그러나": "↔",
        "하지만": "↔",
        "또한": "+",
        "그리고": "+",
        "또는": "|",
        "만약": "?",
        "만일": "?",
        "그러면": "→",
        "결과": "⊕",
        "원인": "⊙",
        "목적": "◎",
        "방법": "⚙",
        "주의": "⚠",
        "중요": "★",
        "필수": "!",
        "선택": "○",
        "성공": "✓",
        "실패": "✗",
        "버그": "🐛",
        "수정": "🔧",
        "배포": "🚀",
        "테스트": "🧪",
    }
    
    COMPRESSION_RULES = [
        ("입니다", ""),
        ("있습니다", "+"),
        ("없습니다", "-"),
        ("합니다", "."),
        ("되어야 합니다", "→!"),
        ("해야 합니다", "→!"),
        ("필요합니다", "!"),
        ("가능합니다", "✓"),
        ("불가능합니다", "✗"),
        ("중요합니다", "★!"),
        ("필수입니다", "!"),
    ]
    
    def compress(self, text: str) -> str:
        if not text:
            return text
        
        result = text
        
        for keyword, symbol in self.KEYWORD_MAP.items():
            result = result.replace(keyword, f" {symbol} ")
        
        for full, compressed in self.COMPRESSION_RULES:
            result = result.replace(full, compressed)
        
        while "  " in result:
            result = result.replace("  ", " ")
        
        return result.strip()
    
    def compress_node(self, node: Node) -> int:
        original_length = len(node.description or "")
        
        if node.description:
            node.description = self.compress(node.description)
        
        for key, value in node.metadata.items():
            if isinstance(value, str):
                node.metadata[key] = self.compress(value)
        
        compressed_length = len(node.description or "")
        tokens_saved = max(0, (original_length - compressed_length) // 4)
        
        node.tokens_saved = tokens_saved
        return tokens_saved
    
    def estimate_tokens(self, text: str) -> int:
        korean_chars = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3')
        other_chars = len(text) - korean_chars
        return (korean_chars // 2) + (other_chars // 4)

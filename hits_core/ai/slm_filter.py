"""SLM-based pre-filter for token cost optimization."""

from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ContentImportance(str, Enum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    NOISE = "noise"


@dataclass
class FilterResult:
    content: str
    importance: ContentImportance
    confidence: float
    keywords: list[str]


CRITICAL_KEYWORDS = [
    "장애", "에러", "버그", "핫픽스", "긴급", "중단", "실패",
    "롤백", "복구", "보안", "취약점", "인증", "권한",
]

IMPORTANT_KEYWORDS = [
    "배포", "빌드", "테스트", "설정", "구성", "변경",
    "업데이트", "수정", "개선", "최적화", "성능",
]

NOISE_PATTERNS = [
    "로그:", "debug:", "trace:", "info:",
    "TODO:", "FIXME:", "XXX:",
]


class SLMFilter:
    def __init__(
        self,
        critical_threshold: float = 0.7,
        important_threshold: float = 0.5,
    ):
        self.critical_threshold = critical_threshold
        self.important_threshold = important_threshold
    
    def classify(self, content: str) -> FilterResult:
        if not content:
            return FilterResult(
                content=content,
                importance=ContentImportance.NOISE,
                confidence=1.0,
                keywords=[],
            )
        
        keywords = []
        critical_score = 0.0
        important_score = 0.0
        noise_score = 0.0
        
        content_lower = content.lower()
        
        for keyword in CRITICAL_KEYWORDS:
            if keyword in content:
                critical_score += 1.0
                keywords.append(keyword)
        
        for keyword in IMPORTANT_KEYWORDS:
            if keyword in content:
                important_score += 0.5
                keywords.append(keyword)
        
        for pattern in NOISE_PATTERNS:
            if pattern.lower() in content_lower:
                noise_score += 0.5
        
        total_chars = max(len(content), 1)
        
        # Score normalization: each keyword contributes meaningfully
        # Critical: even 1 keyword should be enough for critical content
        critical_score = min(critical_score / 2.0, 1.0)
        important_score = min(important_score / 3.0, 1.0)
        noise_score = min(noise_score / 1.0, 1.0)
        
        # Decision: critical takes priority over noise
        # "긴급 장애 발생" has both critical and noise-like exclamation
        # but the critical keywords should dominate
        if critical_score > 0:
            importance = ContentImportance.CRITICAL
            confidence = critical_score
        elif noise_score > important_score and noise_score >= 0.5:
            importance = ContentImportance.NOISE
            confidence = noise_score
        elif important_score > 0:
            importance = ContentImportance.IMPORTANT
            confidence = important_score
        else:
            importance = ContentImportance.IMPORTANT
            confidence = 0.5
        
        return FilterResult(
            content=content,
            importance=importance,
            confidence=confidence,
            keywords=keywords,
        )
    
    def filter_batch(self, contents: list[str]) -> tuple[list[str], list[str]]:
        critical_important = []
        noise = []
        
        for content in contents:
            result = self.classify(content)
            if result.importance in (ContentImportance.CRITICAL, ContentImportance.IMPORTANT):
                critical_important.append(content)
            else:
                noise.append(content)
        
        return critical_important, noise
    
    def estimate_filter_ratio(self, contents: list[str]) -> float:
        if not contents:
            return 0.0
        
        critical_important, _ = self.filter_batch(contents)
        return len(critical_important) / len(contents)

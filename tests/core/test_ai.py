"""Test AI compression."""

import pytest
from hits_core.ai.compressor import SemanticCompressor
from hits_core.ai.slm_filter import SLMFilter, ContentImportance
from hits_core.models.node import Node, NodeLayer


def test_compressor_basic():
    compressor = SemanticCompressor()
    
    original = "따라서 이 기능은 중요합니다."
    compressed = compressor.compress(original)
    
    assert "→" in compressed
    # "중요" is compressed to "★" by KEYWORD_MAP, then "합니다" to "."
    assert "★" in compressed


def test_compressor_node():
    compressor = SemanticCompressor()
    
    node = Node(
        id="test",
        layer=NodeLayer.WHY,
        title="Test Node",
        description="따라서 이 작업은 필수입니다. 그러나 주의해야 합니다."
    )
    
    tokens_saved = compressor.compress_node(node)
    assert tokens_saved >= 0
    assert node.tokens_saved == tokens_saved


def test_compressor_estimate_tokens():
    compressor = SemanticCompressor()
    
    korean_text = "한글테스트입니다"
    mixed_text = "한글 and English text"
    
    kr_tokens = compressor.estimate_tokens(korean_text)
    mixed_tokens = compressor.estimate_tokens(mixed_text)
    
    assert kr_tokens > 0
    assert mixed_tokens > 0


def test_slm_filter_critical():
    filter = SLMFilter()
    
    critical_text = "긴급 장애 발생! 서비스 중단됨"
    result = filter.classify(critical_text)
    
    assert result.importance == ContentImportance.CRITICAL
    assert "장애" in result.keywords or "중단" in result.keywords


def test_slm_filter_noise():
    filter = SLMFilter()
    
    noise_text = "debug: logging info trace message"
    result = filter.classify(noise_text)
    
    assert result.importance == ContentImportance.NOISE


def test_slm_filter_batch():
    filter = SLMFilter()
    
    contents = [
        "장애 발생으로 인한 긴급 조치 필요",
        "debug: routine log message",
        "배포 프로세스 업데이트",
        "trace: function entry point",
    ]
    
    important, noise = filter.filter_batch(contents)
    
    assert len(important) >= 2
    assert len(noise) >= 1

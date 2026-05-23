"""
Tests for engine/extractor.py — all HTTP calls are mocked.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from engine.extractor import (
    ExtractionError,
    LLMError,
    complete,
    draft,
    extract,
)
from engine.schemas import BuyIntakeExtraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(content: str, tokens: int = 10, status: int = 200):
    resp = MagicMock()
    resp.ok = status < 400
    resp.status_code = status
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": tokens},
    }
    resp.text = content
    return resp


VALID_BUY_JSON = json.dumps({
    "full_name": "Alice Smith",
    "email": "alice@example.com",
    "jurisdiction": "england",
    "budget_min": 300_000,
    "budget_max": 450_000,
    "locations": ["Reading"],
    "bedrooms_min": 3,
    "property_types": ["house"],
    "must_haves": ["garden"],
    "nice_to_haves": [],
    "first_time_buyer": False,
})


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


def test_complete_returns_content(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("requests.post", return_value=_mock_response("hello world", 5)):
        content, tokens = complete([{"role": "user", "content": "ping"}])
    assert content == "hello world"
    assert tokens == 5


def test_complete_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="OPENROUTER_API_KEY"):
        complete([{"role": "user", "content": "ping"}])


def test_complete_rate_limit_retries(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    rate_limited = _mock_response("", status=429)
    rate_limited.ok = False
    rate_limited.status_code = 429
    success = _mock_response("ok", tokens=3)

    call_count = 0
    def fake_post(*a, **kw):
        nonlocal call_count
        call_count += 1
        return rate_limited if call_count < 3 else success

    with patch("requests.post", side_effect=fake_post):
        with patch("time.sleep"):  # don't actually sleep in tests
            content, _ = complete([{"role": "user", "content": "ping"}])
    assert content == "ok"


def test_complete_all_retries_exhausted_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    import requests as req_module

    def always_fail(*a, **kw):
        raise req_module.RequestException("timeout")

    with patch("requests.post", side_effect=always_fail):
        with patch("time.sleep"):
            with pytest.raises(LLMError, match="exhausted"):
                complete([{"role": "user", "content": "ping"}])


# ---------------------------------------------------------------------------
# extract()
# ---------------------------------------------------------------------------


def test_extract_valid_schema(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("requests.post", return_value=_mock_response(VALID_BUY_JSON, 20)):
        result, tokens = extract("extract requirements", BuyIntakeExtraction)
    assert isinstance(result, BuyIntakeExtraction)
    assert result.budget_max == 450_000
    assert tokens == 20


def test_extract_strips_markdown_fences(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    fenced = f"```json\n{VALID_BUY_JSON}\n```"
    with patch("requests.post", return_value=_mock_response(fenced, 20)):
        result, _ = extract("extract", BuyIntakeExtraction)
    assert result.full_name == "Alice Smith"


def test_extract_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("requests.post", return_value=_mock_response("not json at all")):
        with pytest.raises(ExtractionError, match="non-JSON"):
            extract("extract", BuyIntakeExtraction)


def test_extract_schema_violation_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    # budget_max < budget_min violates the validator
    bad = json.dumps({**json.loads(VALID_BUY_JSON), "budget_max": 100_000})
    with patch("requests.post", return_value=_mock_response(bad)):
        with pytest.raises(ExtractionError, match="validation"):
            extract("extract", BuyIntakeExtraction)


# ---------------------------------------------------------------------------
# draft()
# ---------------------------------------------------------------------------


def test_draft_returns_text(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("requests.post", return_value=_mock_response("Dear vendor,\n\nWe offer...", 15)):
        text, tokens = draft("draft offer letter")
    assert "vendor" in text
    assert tokens == 15

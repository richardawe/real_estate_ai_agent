"""Tests for the listings adapter runtime (no real HTTP calls)."""

import pytest
from unittest.mock import MagicMock, patch

from adapters_runtime.listings_runtime import (
    AdapterAbortError,
    _parse_currency_int,
    _parse_int_first,
    build_search_url,
    load_adapter,
    run_http_search,
)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("£425,000", 425_000),
    ("£1,500 pcm", 1_500),
    ("$2,200 / mo", 2_200),
    ("350000", 350_000),
])
def test_parse_currency_int(text, expected):
    assert _parse_currency_int(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("3 bed", 3),
    ("2br / 1ba", 2),
    ("Studio", None),
])
def test_parse_int_first(text, expected):
    assert _parse_int_first(text) == expected


# ---------------------------------------------------------------------------
# load_adapter
# ---------------------------------------------------------------------------


def test_load_zoopla():
    adapter = load_adapter("zoopla")
    assert adapter["source_id"] == "zoopla"
    assert adapter["runtime"] == "playwright"


def test_load_rightmove():
    adapter = load_adapter("rightmove")
    assert adapter["source_id"] == "rightmove"


def test_load_craigslist():
    adapter = load_adapter("craigslist")
    assert adapter["source_id"] == "craigslist"


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="unknown_source"):
        load_adapter("unknown_source")


# ---------------------------------------------------------------------------
# build_search_url
# ---------------------------------------------------------------------------


def test_build_buy_url_zoopla():
    adapter = load_adapter("zoopla")
    req = {"budget_min": 300_000, "budget_max": 450_000, "bedrooms_min": 3}
    url = build_search_url(adapter, "buy", req, "reading")
    assert "reading" in url
    assert "300000" in url
    assert "450000" in url
    assert "3" in url


def test_build_rent_url_craigslist():
    adapter = load_adapter("craigslist")
    req = {"rent_min": 1_000, "rent_max": 2_000, "bedrooms_min": 2}
    url = build_search_url(adapter, "rent", req, "sfbay")
    assert "1000" in url
    assert "2000" in url


# ---------------------------------------------------------------------------
# run_http_search — mocked
# ---------------------------------------------------------------------------


def _mock_resp(status: int, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.text = text
    return r


def test_run_http_aborts_on_403():
    adapter = load_adapter("craigslist")
    with patch("requests.get", return_value=_mock_resp(403)):
        with patch.object(
            __import__("adapters_runtime.listings_runtime", fromlist=["_check_robots"]),
            "_check_robots",
            return_value=True,
        ):
            with pytest.raises(AdapterAbortError) as exc_info:
                run_http_search(adapter, "https://example.com/search", max_pages=1)
    assert exc_info.value.status_code == 403


def test_run_http_aborts_on_429():
    adapter = load_adapter("craigslist")
    with patch("requests.get", return_value=_mock_resp(429)):
        with patch(
            "adapters_runtime.listings_runtime._check_robots", return_value=True
        ):
            with pytest.raises(AdapterAbortError) as exc_info:
                run_http_search(adapter, "https://example.com/search", max_pages=1)
    assert exc_info.value.status_code == 429


def test_run_http_returns_empty_on_empty_html():
    adapter = load_adapter("craigslist")
    with patch("requests.get", return_value=_mock_resp(200, "<html></html>")):
        with patch(
            "adapters_runtime.listings_runtime._check_robots", return_value=True
        ):
            results = run_http_search(adapter, "https://example.com/search", max_pages=1)
    assert results == []


def test_run_http_stops_on_not_ok():
    adapter = load_adapter("craigslist")
    responses = [_mock_resp(200, "<html></html>"), _mock_resp(404)]
    with patch("requests.get", side_effect=responses):
        with patch(
            "adapters_runtime.listings_runtime._check_robots", return_value=True
        ):
            with patch("time.sleep"):
                results = run_http_search(adapter, "https://example.com/search", max_pages=2)
    assert results == []

"""Tests for the cache status script.

The HTTP side runs against httpx.MockTransport; the token is real, so the API's
own decoder checks it. ``scripts/`` is not a package, so the module is loaded by path.
"""

import importlib.util
from pathlib import Path

import httpx
import pytest

from app.utils.security import decode_access_token

_SPEC = importlib.util.spec_from_file_location("cache_status", Path(__file__).with_name("cache_status.py"))
cache_status = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cache_status)

STATUS = {"enabled": True, "entries": 3, "bytes": 2 * 1024 * 1024, "max_bytes": 64 * 1024 * 1024,
          "hits": 30, "misses": 10, "stale": 4, "bypassed": 1, "stored": 10}


def client_answering(status_code: int = 200, seen: list | None = None) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status_code, json=STATUS)

    return httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handle))


class TestMintToken:
    def test_is_a_valid_admin_access_token(self):
        payload = decode_access_token(cache_status.mint_token(1))
        assert payload["sub"] == "1" and payload["type"] == "access"

    def test_expires_within_a_minute(self):
        payload = decode_access_token(cache_status.mint_token(1))
        assert payload["exp"] - payload["iat"] <= 60


class TestFetch:
    def test_reads_status_with_a_bearer_token(self):
        seen = []
        assert cache_status.fetch(client_answering(seen=seen), "tok") == STATUS
        assert (seen[0].method, seen[0].url.path) == ("GET", "/admin/cache")
        assert seen[0].headers["authorization"] == "Bearer tok"

    def test_clear_posts(self):
        seen = []
        cache_status.fetch(client_answering(seen=seen), "tok", clear=True)
        assert (seen[0].method, seen[0].url.path) == ("POST", "/admin/cache/clear")

    @pytest.mark.parametrize("code, hint", [(401, "SECRET_KEY"), (403, "not a site admin")])
    def test_refusals_explain_themselves(self, code, hint):
        with pytest.raises(SystemExit, match=hint):
            cache_status.fetch(client_answering(code), "tok")


class TestSummarize:
    def test_computes_the_hit_rate(self):
        text = cache_status.summarize(STATUS)
        assert "75.0%" in text and "30 hits / 40 lookups" in text
        assert "2.0 of 64 MB" in text

    def test_no_lookups_yet(self):
        assert "n/a" in cache_status.summarize({**STATUS, "hits": 0, "misses": 0})


class TestMain:
    def test_requires_an_admin_id(self, monkeypatch):
        monkeypatch.delenv("SPINSHARE_ADMIN_ID", raising=False)
        with pytest.raises(SystemExit):
            cache_status.main([])

    def test_unreachable_api_is_reported_plainly(self):
        with pytest.raises(SystemExit, match="Could not reach the API"):
            cache_status.main(["--admin-id", "1", "--base-url", "http://127.0.0.1:9"])

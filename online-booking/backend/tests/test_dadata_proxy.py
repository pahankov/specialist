"""Tests for DaData proxy endpoint (P1-3).

Regression: proxy ignored the client payload (json=None) and re-raised
upstream errors as bare 500s instead of 502.
"""
import httpx
import pytest

import importlib
import sys

# NOTE: app.modules.dadata.__init__ re-exports the name `router` (APIRouter),
# which shadows the submodule attribute — resolve via sys.modules explicitly.
import app.modules.dadata.router  # noqa: F401 (ensures sys.modules entry)
dadata_router = sys.modules["app.modules.dadata.router"]


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal stand-in for httpx.AsyncClient (captures outgoing JSON)."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.sent = []
        _FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.sent.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse({"ok": True, "echo": json})


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    monkeypatch.setattr(dadata_router.settings, "DADATA_API_KEY", "test-token")
    monkeypatch.setattr(dadata_router.settings, "DADATA_SECRET", "test-secret")
    _FakeClient.instances.clear()
    monkeypatch.setattr(dadata_router.httpx, "AsyncClient", _FakeClient)


class TestDadataProxy:
    async def test_forwards_client_body(self, client):
        """Client payload must reach DaData (was json=None)."""
        payload = {"query": "Москва", "count": 5}
        resp = await client.post("/api/dadata/suggest/address", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "echo": payload}
        assert _FakeClient.instances, "upstream must be called"
        sent = _FakeClient.instances[0].sent[0]
        assert sent["json"] == payload
        assert sent["url"].endswith("/4_1/rs/suggest/address")

    async def test_forwards_auth_headers(self, client):
        """Upstream must receive Token auth + secret (no credential leak to caller)."""
        await client.post("/api/dadata/suggest/address", json={"query": "x"})
        headers = _FakeClient.instances[0].sent[0]["headers"]
        assert headers["Authorization"] == "Token test-token"
        assert headers["X-Secret"] == "test-secret"
        assert "test-secret" not in str(headers.get("Authorization", ""))

    async def test_503_without_credentials(self, client, monkeypatch):
        """Missing env credentials -> 503, no upstream call."""
        monkeypatch.setattr(dadata_router.settings, "DADATA_API_KEY", "")
        monkeypatch.setattr(dadata_router.settings, "DADATA_SECRET", "")
        before = len(_FakeClient.instances)
        resp = await client.post("/api/dadata/suggest/address", json={"query": "x"})
        assert resp.status_code == 503
        assert len(_FakeClient.instances) == before

    async def test_502_on_upstream_error(self, client, monkeypatch):
        """Upstream failure -> 502 (was bare re-raise -> 500)."""

        class _FailClient(_FakeClient):
            async def post(self, url, headers=None, json=None):
                raise httpx.ConnectError("boom")

        monkeypatch.setattr(dadata_router.httpx, "AsyncClient", _FailClient)
        resp = await client.post("/api/dadata/suggest/address", json={"query": "x"})
        assert resp.status_code == 502

    async def test_mirrors_upstream_status(self, client, monkeypatch):
        """Upstream 4xx (e.g. bad DaData key) is mirrored, not masked as 200."""

        class _DeniedClient(_FakeClient):
            async def post(self, url, headers=None, json=None):
                self.sent.append({"url": url, "headers": headers, "json": json})
                return _FakeResponse({"family": "CLIENT_ERROR"}, status_code=401)

        monkeypatch.setattr(dadata_router.httpx, "AsyncClient", _DeniedClient)
        resp = await client.post("/api/dadata/suggest/address", json={"query": "x"})
        assert resp.status_code == 401

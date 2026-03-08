"""Tests for the kAIs HTTP client — uses respx to mock httpx requests."""

from __future__ import annotations

import json
import os

import httpx
import pytest
import respx

from kais import KaisHTTPClient, KaisAPIError, KaisAuthError, KaisNotFoundError


BASE_URL = "http://test-api:8080"
NS = "test-ns"
NS_BASE = f"{BASE_URL}/api/v1/namespaces/{NS}"


@pytest.fixture()
def client():
    """Create a KaisHTTPClient pointed at the test base URL."""
    return KaisHTTPClient(base_url=BASE_URL, api_key="test-key", namespace=NS)


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestURLConstruction:
    def test_ns_base(self, client: KaisHTTPClient) -> None:
        assert client._ns_base == NS_BASE

    def test_default_values_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KAIS_API_URL", "http://env-api:9090")
        monkeypatch.setenv("KAIS_API_KEY", "env-key")
        monkeypatch.setenv("KAIS_NAMESPACE", "env-ns")
        c = KaisHTTPClient()
        assert c._base_url == "http://env-api:9090"
        assert c._api_key == "env-key"
        assert c._namespace == "env-ns"

    def test_defaults_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KAIS_API_URL", raising=False)
        monkeypatch.delenv("KAIS_API_KEY", raising=False)
        monkeypatch.delenv("KAIS_NAMESPACE", raising=False)
        c = KaisHTTPClient()
        assert c._base_url == "http://localhost:8080"
        assert c._api_key is None
        assert c._namespace == "default"

    def test_trailing_slash_stripped(self) -> None:
        c = KaisHTTPClient(base_url="http://example.com/")
        assert c._base_url == "http://example.com"


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


class TestAuth:
    def test_bearer_token_header(self, client: KaisHTTPClient) -> None:
        http = client._ensure_client()
        assert http.headers["authorization"] == "Bearer test-key"

    def test_session_cookie(self) -> None:
        c = KaisHTTPClient(
            base_url=BASE_URL, session_cookie="sess-abc", namespace=NS
        )
        http = c._ensure_client()
        assert http.cookies.get("ory_kratos_session") == "sess-abc"

    def test_no_auth_when_not_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KAIS_API_KEY", raising=False)
        c = KaisHTTPClient(base_url=BASE_URL, namespace=NS)
        http = c._ensure_client()
        assert "authorization" not in http.headers


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCellsClient:
    @respx.mock
    async def test_list_cells(self, client: KaisHTTPClient) -> None:
        route = respx.get(f"{NS_BASE}/cells").mock(
            return_value=httpx.Response(200, json=[{"name": "dev-0"}])
        )
        result = await client.cells.list()
        assert result == [{"name": "dev-0"}]
        assert route.called

    @respx.mock
    async def test_get_cell(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells/dev-0").mock(
            return_value=httpx.Response(200, json={"name": "dev-0", "status": "Running"})
        )
        result = await client.cells.get("dev-0")
        assert result["name"] == "dev-0"

    @respx.mock
    async def test_create_cell(self, client: KaisHTTPClient) -> None:
        spec = {"name": "new-cell", "model": "claude-sonnet"}
        respx.post(f"{NS_BASE}/cells").mock(
            return_value=httpx.Response(201, json={"name": "new-cell"})
        )
        result = await client.cells.create(spec)
        assert result["name"] == "new-cell"

    @respx.mock
    async def test_update_cell(self, client: KaisHTTPClient) -> None:
        respx.put(f"{NS_BASE}/cells/dev-0").mock(
            return_value=httpx.Response(200, json={"name": "dev-0", "model": "claude-opus"})
        )
        result = await client.cells.update("dev-0", {"model": "claude-opus"})
        assert result["model"] == "claude-opus"

    @respx.mock
    async def test_delete_cell(self, client: KaisHTTPClient) -> None:
        respx.delete(f"{NS_BASE}/cells/dev-0").mock(
            return_value=httpx.Response(204)
        )
        await client.cells.delete("dev-0")

    @respx.mock
    async def test_chat(self, client: KaisHTTPClient) -> None:
        respx.post(f"{NS_BASE}/cells/dev-0/messages").mock(
            return_value=httpx.Response(200, json={"content": "Hello back!"})
        )
        result = await client.cells.chat("dev-0", "Hello!")
        assert result["content"] == "Hello back!"

    @respx.mock
    async def test_history(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells/dev-0/history").mock(
            return_value=httpx.Response(200, json=[{"content": "msg1"}, {"content": "msg2"}])
        )
        result = await client.cells.history("dev-0")
        assert len(result) == 2

    @respx.mock
    async def test_events(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells/dev-0/events").mock(
            return_value=httpx.Response(200, json=[{"type": "tool_use"}])
        )
        result = await client.cells.events("dev-0")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Formations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFormationsClient:
    @respx.mock
    async def test_list_formations(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/formations").mock(
            return_value=httpx.Response(200, json=[{"name": "my-form"}])
        )
        result = await client.formations.list()
        assert result == [{"name": "my-form"}]

    @respx.mock
    async def test_get_formation(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/formations/my-form").mock(
            return_value=httpx.Response(200, json={"name": "my-form"})
        )
        result = await client.formations.get("my-form")
        assert result["name"] == "my-form"

    @respx.mock
    async def test_create_formation(self, client: KaisHTTPClient) -> None:
        respx.post(f"{NS_BASE}/formations").mock(
            return_value=httpx.Response(201, json={"name": "new-form"})
        )
        result = await client.formations.create({"name": "new-form"})
        assert result["name"] == "new-form"

    @respx.mock
    async def test_update_formation(self, client: KaisHTTPClient) -> None:
        respx.put(f"{NS_BASE}/formations/my-form").mock(
            return_value=httpx.Response(200, json={"name": "my-form"})
        )
        result = await client.formations.update("my-form", {"topology": "star"})
        assert result["name"] == "my-form"

    @respx.mock
    async def test_delete_formation(self, client: KaisHTTPClient) -> None:
        respx.delete(f"{NS_BASE}/formations/my-form").mock(
            return_value=httpx.Response(204)
        )
        await client.formations.delete("my-form")


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRulesClient:
    @respx.mock
    async def test_list_rules(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/rules").mock(
            return_value=httpx.Response(200, json=[{"id": "r1"}])
        )
        result = await client.rules.list()
        assert len(result) == 1

    @respx.mock
    async def test_get_rule(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/rules/r1").mock(
            return_value=httpx.Response(200, json={"id": "r1", "content": "be nice"})
        )
        result = await client.rules.get("r1")
        assert result["id"] == "r1"

    @respx.mock
    async def test_create_rule(self, client: KaisHTTPClient) -> None:
        respx.post(f"{NS_BASE}/rules").mock(
            return_value=httpx.Response(201, json={"id": "r2"})
        )
        result = await client.rules.create({"content": "new rule"})
        assert result["id"] == "r2"

    @respx.mock
    async def test_update_rule(self, client: KaisHTTPClient) -> None:
        respx.put(f"{NS_BASE}/rules/r1").mock(
            return_value=httpx.Response(200, json={"id": "r1", "content": "updated"})
        )
        result = await client.rules.update("r1", {"content": "updated"})
        assert result["content"] == "updated"

    @respx.mock
    async def test_delete_rule(self, client: KaisHTTPClient) -> None:
        respx.delete(f"{NS_BASE}/rules/r1").mock(
            return_value=httpx.Response(204)
        )
        await client.rules.delete("r1")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFilesClient:
    @respx.mock
    async def test_list_files(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/files").mock(
            return_value=httpx.Response(200, json=[{"path": "data.csv"}])
        )
        result = await client.files.list()
        assert result == [{"path": "data.csv"}]

    @respx.mock
    async def test_download(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/files/data.csv").mock(
            return_value=httpx.Response(200, content=b"col1,col2\n1,2\n")
        )
        data = await client.files.download("data.csv")
        assert data == b"col1,col2\n1,2\n"

    @respx.mock
    async def test_delete_file(self, client: KaisHTTPClient) -> None:
        respx.delete(f"{NS_BASE}/files/data.csv").mock(
            return_value=httpx.Response(204)
        )
        await client.files.delete("data.csv")


# ---------------------------------------------------------------------------
# Completions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCompletionsClient:
    @respx.mock
    async def test_create_non_streaming(self, client: KaisHTTPClient) -> None:
        respx.post(f"{NS_BASE}/cells/dev-0/completions").mock(
            return_value=httpx.Response(200, json={"content": "42", "model": "claude"})
        )
        result = await client.completions.create("dev-0", "What is 6*7?")
        assert result["content"] == "42"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrors:
    @respx.mock
    async def test_404_raises_not_found(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells/nonexistent").mock(
            return_value=httpx.Response(404, json={"error": "cell not found"})
        )
        with pytest.raises(KaisNotFoundError) as exc_info:
            await client.cells.get("nonexistent")
        assert exc_info.value.status_code == 404
        assert "cell not found" in exc_info.value.detail

    @respx.mock
    async def test_401_raises_auth_error(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells").mock(
            return_value=httpx.Response(401, json={"error": "invalid token"})
        )
        with pytest.raises(KaisAuthError) as exc_info:
            await client.cells.list()
        assert exc_info.value.status_code == 401

    @respx.mock
    async def test_403_raises_auth_error(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells").mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )
        with pytest.raises(KaisAuthError) as exc_info:
            await client.cells.list()
        assert exc_info.value.status_code == 403

    @respx.mock
    async def test_500_raises_api_error(self, client: KaisHTTPClient) -> None:
        respx.get(f"{NS_BASE}/cells").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(KaisAPIError) as exc_info:
            await client.cells.list()
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHealth:
    @respx.mock
    async def test_health_ok(self, client: KaisHTTPClient) -> None:
        respx.get(f"{BASE_URL}/healthz").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        assert await client.health() is True

    @respx.mock
    async def test_health_down(self, client: KaisHTTPClient) -> None:
        respx.get(f"{BASE_URL}/healthz").mock(
            return_value=httpx.Response(503)
        )
        assert await client.health() is False


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextManager:
    async def test_async_context_manager(self) -> None:
        async with KaisHTTPClient(base_url=BASE_URL, namespace=NS) as client:
            assert client._client is not None
            assert not client._client.is_closed
        assert client._client is None

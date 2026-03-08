"""Resource clients for the kAIs HTTP API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx


class KaisAPIError(Exception):
    """Raised when the kAIs API returns a non-success status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class KaisNotFoundError(KaisAPIError):
    """Raised when a resource is not found (404)."""

    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(404, detail)


class KaisAuthError(KaisAPIError):
    """Raised on authentication/authorization failure (401/403)."""

    def __init__(self, status_code: int = 401, detail: str = "Unauthorized") -> None:
        super().__init__(status_code, detail)


def _check_response(resp: httpx.Response) -> None:
    """Raise an appropriate exception for non-2xx responses."""
    if resp.is_success:
        return
    try:
        body = resp.json()
        detail = body.get("error", resp.text)
    except Exception:
        detail = resp.text
    if resp.status_code == 404:
        raise KaisNotFoundError(detail)
    if resp.status_code in (401, 403):
        raise KaisAuthError(resp.status_code, detail)
    raise KaisAPIError(resp.status_code, detail)


class _BaseResourceClient:
    """Base class providing shared HTTP helpers."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url

    def _url(self, *parts: str) -> str:
        segments = "/".join(parts)
        if segments:
            return f"{self._base_url}/{segments}"
        return self._base_url


class CellsClient(_BaseResourceClient):
    """Client for /api/v1/namespaces/{ns}/cells."""

    async def list(self) -> list[dict[str, Any]]:
        """List all cells in the namespace."""
        resp = await self._client.get(self._url())
        _check_response(resp)
        return resp.json()

    async def get(self, name: str) -> dict[str, Any]:
        """Get a cell by name."""
        resp = await self._client.get(self._url(name))
        _check_response(resp)
        return resp.json()

    async def create(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create a new cell."""
        resp = await self._client.post(self._url(), json=spec)
        _check_response(resp)
        return resp.json()

    async def update(self, name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Update an existing cell."""
        resp = await self._client.put(self._url(name), json=spec)
        _check_response(resp)
        return resp.json()

    async def delete(self, name: str) -> None:
        """Delete a cell."""
        resp = await self._client.delete(self._url(name))
        _check_response(resp)

    async def chat(self, name: str, message: str) -> dict[str, Any]:
        """Send a message to a cell. POST /cells/{name}/messages."""
        resp = await self._client.post(
            self._url(name, "messages"),
            json={"content": message},
        )
        _check_response(resp)
        return resp.json()

    async def history(self, name: str) -> list[dict[str, Any]]:
        """Get the chat history for a cell. GET /cells/{name}/history."""
        resp = await self._client.get(self._url(name, "history"))
        _check_response(resp)
        return resp.json()

    async def events(self, name: str) -> list[dict[str, Any]]:
        """Get events for a cell. GET /cells/{name}/events."""
        resp = await self._client.get(self._url(name, "events"))
        _check_response(resp)
        return resp.json()


class FormationsClient(_BaseResourceClient):
    """Client for /api/v1/namespaces/{ns}/formations."""

    async def list(self) -> list[dict[str, Any]]:
        """List all formations in the namespace."""
        resp = await self._client.get(self._url())
        _check_response(resp)
        return resp.json()

    async def get(self, name: str) -> dict[str, Any]:
        """Get a formation by name."""
        resp = await self._client.get(self._url(name))
        _check_response(resp)
        return resp.json()

    async def create(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create a new formation."""
        resp = await self._client.post(self._url(), json=spec)
        _check_response(resp)
        return resp.json()

    async def update(self, name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Update an existing formation."""
        resp = await self._client.put(self._url(name), json=spec)
        _check_response(resp)
        return resp.json()

    async def delete(self, name: str) -> None:
        """Delete a formation."""
        resp = await self._client.delete(self._url(name))
        _check_response(resp)


class RulesClient(_BaseResourceClient):
    """Client for /api/v1/namespaces/{ns}/rules."""

    async def list(self) -> list[dict[str, Any]]:
        """List all rules in the namespace."""
        resp = await self._client.get(self._url())
        _check_response(resp)
        return resp.json()

    async def get(self, id: str) -> dict[str, Any]:
        """Get a rule by ID."""
        resp = await self._client.get(self._url(id))
        _check_response(resp)
        return resp.json()

    async def create(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Create a new rule."""
        resp = await self._client.post(self._url(), json=rule)
        _check_response(resp)
        return resp.json()

    async def update(self, id: str, rule: dict[str, Any]) -> dict[str, Any]:
        """Update an existing rule."""
        resp = await self._client.put(self._url(id), json=rule)
        _check_response(resp)
        return resp.json()

    async def delete(self, id: str) -> None:
        """Delete a rule."""
        resp = await self._client.delete(self._url(id))
        _check_response(resp)


class FilesClient(_BaseResourceClient):
    """Client for /api/v1/namespaces/{ns}/files."""

    async def list(self) -> list[dict[str, Any]]:
        """List all files in the namespace."""
        resp = await self._client.get(self._url())
        _check_response(resp)
        return resp.json()

    async def upload(self, file_path: str) -> dict[str, Any]:
        """Upload a file. Sends as multipart/form-data."""
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            resp = await self._client.post(
                self._url(),
                files={"file": (filename, f)},
            )
        _check_response(resp)
        return resp.json()

    async def download(self, path: str) -> bytes:
        """Download a file by path. Returns raw bytes."""
        # Files use wildcard routes: GET /files/*
        resp = await self._client.get(self._url(path))
        _check_response(resp)
        return resp.content

    async def delete(self, path: str) -> None:
        """Delete a file by path."""
        resp = await self._client.delete(self._url(path))
        _check_response(resp)


class CompletionsClient(_BaseResourceClient):
    """Client for /api/v1/namespaces/{ns}/cells/{name}/completions."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        # base_url here is the cells base URL
        super().__init__(client, base_url)

    async def create(
        self,
        cell_name: str,
        message: str,
        *,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Create a completion from a cell.

        Args:
            cell_name: Name of the cell to use for completion.
            message: The user message.
            stream: If True, return an async iterator yielding SSE chunks.

        Returns:
            A dict with the full response when ``stream=False``, or an async
            iterator of dicts when ``stream=True``.
        """
        url = self._url(cell_name, "completions")
        payload: dict[str, Any] = {"message": message, "stream": stream}

        if not stream:
            resp = await self._client.post(url, json=payload)
            _check_response(resp)
            return resp.json()

        return self._stream(url, payload)

    async def _stream(
        self, url: str, payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Internal: SSE streaming request."""
        import json

        async with self._client.stream("POST", url, json=payload) as resp:
            if not resp.is_success:
                await resp.aread()
                _check_response(resp)
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: ") :]
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue

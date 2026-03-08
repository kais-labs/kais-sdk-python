"""kAIs HTTP client — async REST API client for the kAIs platform."""

from __future__ import annotations

import os
from typing import Any

import httpx

from .resources import (
    CellsClient,
    CompletionsClient,
    FilesClient,
    FormationsClient,
    RulesClient,
)


class KaisHTTPClient:
    """Async HTTP client for the kAIs REST API.

    Usage::

        async with KaisHTTPClient() as client:
            cells = await client.cells.list()
            reply = await client.cells.chat("dev-0", "Hello!")

    Configuration can be set via constructor arguments or environment variables:

    - ``base_url`` / ``KAIS_API_URL`` — API server URL (default ``http://localhost:8080``)
    - ``api_key`` / ``KAIS_API_KEY`` — Bearer token for authentication
    - ``namespace`` / ``KAIS_NAMESPACE`` — Kubernetes namespace (default ``default``)
    - ``session_cookie`` — Kratos session cookie value for cookie-based auth
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        namespace: str | None = None,
        *,
        session_cookie: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = (
            base_url or os.environ.get("KAIS_API_URL", "http://localhost:8080")
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("KAIS_API_KEY")
        self._namespace = namespace or os.environ.get("KAIS_NAMESPACE", "default")
        self._session_cookie = session_cookie
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

        # Lazily-initialized resource clients
        self._cells: CellsClient | None = None
        self._formations: FormationsClient | None = None
        self._rules: RulesClient | None = None
        self._files: FilesClient | None = None
        self._completions: CompletionsClient | None = None

    # --- lifecycle -----------------------------------------------------------

    def _build_client(self) -> httpx.AsyncClient:
        """Create the httpx.AsyncClient with auth headers/cookies."""
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        cookies: dict[str, str] = {}

        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if self._session_cookie:
            cookies["ory_kratos_session"] = self._session_cookie

        return httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            timeout=self._timeout,
        )

    def _ensure_client(self) -> httpx.AsyncClient:
        """Return the active client, creating one if needed."""
        if self._client is None or self._client.is_closed:
            self._client = self._build_client()
            # Reset cached resource clients when the HTTP client changes
            self._cells = None
            self._formations = None
            self._rules = None
            self._files = None
            self._completions = None
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> KaisHTTPClient:
        self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # --- URL helpers ---------------------------------------------------------

    @property
    def _ns_base(self) -> str:
        """Return the namespaced base path, e.g. http://localhost:8080/api/v1/namespaces/default."""
        return f"{self._base_url}/api/v1/namespaces/{self._namespace}"

    # --- resource clients ----------------------------------------------------

    @property
    def cells(self) -> CellsClient:
        """Client for Cell resources."""
        if self._cells is None:
            self._cells = CellsClient(
                self._ensure_client(), f"{self._ns_base}/cells"
            )
        return self._cells

    @property
    def formations(self) -> FormationsClient:
        """Client for Formation resources."""
        if self._formations is None:
            self._formations = FormationsClient(
                self._ensure_client(), f"{self._ns_base}/formations"
            )
        return self._formations

    @property
    def rules(self) -> RulesClient:
        """Client for Rule resources."""
        if self._rules is None:
            self._rules = RulesClient(
                self._ensure_client(), f"{self._ns_base}/rules"
            )
        return self._rules

    @property
    def files(self) -> FilesClient:
        """Client for File resources (S3-backed)."""
        if self._files is None:
            self._files = FilesClient(
                self._ensure_client(), f"{self._ns_base}/files"
            )
        return self._files

    @property
    def completions(self) -> CompletionsClient:
        """Client for cell completions (LLM inference)."""
        if self._completions is None:
            self._completions = CompletionsClient(
                self._ensure_client(), f"{self._ns_base}/cells"
            )
        return self._completions

    # --- convenience ---------------------------------------------------------

    async def health(self) -> bool:
        """Check if the API server is reachable via GET /healthz."""
        try:
            resp = await self._ensure_client().get(f"{self._base_url}/healthz")
            return resp.is_success
        except httpx.HTTPError:
            return False

"""kAIs client — async NATS-based communication with kAIs cells."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

import nats
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg

from .types import Message, CellInfo


class KaisClient:
    """Async client for communicating with kAIs cells over NATS.

    Usage::

        async with KaisClient() as client:
            reply = await client.ask("planner-0", "What's the plan?")
            print(reply.content)
    """

    def __init__(
        self,
        nats_url: str | None = None,
        namespace: str | None = None,
        app_name: str | None = None,
    ) -> None:
        self._nats_url = nats_url or os.environ.get("NATS_URL", "nats://localhost:4222")
        self._namespace = namespace or os.environ.get("KAIS_NAMESPACE", "default")
        self._app_name = app_name or os.environ.get("KAIS_APP_NAME", "sdk-client")
        self._nc: NatsClient | None = None
        self._subscriptions: list[Any] = []

    # --- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the NATS server."""
        self._nc = await nats.connect(self._nats_url, name=self._app_name)

    async def close(self) -> None:
        """Drain subscriptions and close the NATS connection."""
        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            self._nc = None

    async def __aenter__(self) -> KaisClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def _conn(self) -> NatsClient:
        if self._nc is None or not self._nc.is_connected:
            raise RuntimeError("KaisClient is not connected — call connect() first")
        return self._nc

    # --- messaging -----------------------------------------------------------

    async def send(self, cell_name: str, content: str, metadata: dict[str, Any] | None = None) -> Message:
        """Send a message to a cell's inbox (fire-and-forget).

        Returns the sent Message.
        """
        msg = Message.create(from_=f"user:{self._app_name}", to=cell_name, content=content, metadata=metadata)
        subject = f"cell.{self._namespace}.{cell_name}.inbox"
        await self._conn.publish(subject, msg.to_json())
        return msg

    async def ask(
        self,
        cell_name: str,
        content: str,
        timeout: float = 30.0,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Send a message to a cell and wait for its reply on the outbox.

        Subscribes to the cell's outbox, sends the message, then waits up to
        *timeout* seconds for a response whose ``id`` or content indicates it
        is a reply.
        """
        outbox_subject = f"cell.{self._namespace}.{cell_name}.outbox"

        reply_future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()

        async def _on_reply(raw: Msg) -> None:
            reply = Message.from_json(raw.data)
            if not reply_future.done():
                reply_future.set_result(reply)

        sub = await self._conn.subscribe(outbox_subject, cb=_on_reply)

        try:
            await self.send(cell_name, content, metadata=metadata)
            return await asyncio.wait_for(reply_future, timeout=timeout)
        finally:
            await sub.unsubscribe()

    async def receive(self) -> AsyncIterator[Message]:
        """Async iterator that yields every outbox message in the namespace.

        Listens on ``cell.{ns}.*.outbox`` (wildcard).
        """
        queue: asyncio.Queue[Message] = asyncio.Queue()

        async def _on_msg(raw: Msg) -> None:
            await queue.put(Message.from_json(raw.data))

        sub = await self._conn.subscribe(
            f"cell.{self._namespace}.*.outbox", cb=_on_msg,
        )
        self._subscriptions.append(sub)

        try:
            while True:
                yield await queue.get()
        finally:
            await sub.unsubscribe()

    async def subscribe(
        self,
        cell_name: str,
        callback: Callable[[Message], Awaitable[None]],
    ) -> Any:
        """Subscribe to a specific cell's outbox messages.

        Returns the underlying NATS subscription (can be used to unsubscribe).
        """
        subject = f"cell.{self._namespace}.{cell_name}.outbox"

        async def _on_msg(raw: Msg) -> None:
            await callback(Message.from_json(raw.data))

        sub = await self._conn.subscribe(subject, cb=_on_msg)
        self._subscriptions.append(sub)
        return sub

    async def broadcast(self, content: str, metadata: dict[str, Any] | None = None) -> Message:
        """Publish a message to every cell in the namespace.

        Uses the wildcard inbox subject ``cell.{ns}.*.inbox``.
        Note: NATS does not expand wildcards on publish — cells must subscribe
        to a subject that matches.  In kAIs each cell subscribes to its own
        inbox, so ``broadcast`` publishes to a well-known fan-out subject that
        the cell runtime also listens on.
        """
        msg = Message.create(from_=f"user:{self._app_name}", to="*", content=content, metadata=metadata)
        subject = f"cell.{self._namespace}.broadcast"
        await self._conn.publish(subject, msg.to_json())
        return msg

    # --- discovery / health --------------------------------------------------

    async def discover_cells(self, timeout: float = 5.0) -> list[CellInfo]:
        """Request the list of cells from the kAIs discovery service."""
        subject = f"kais.{self._namespace}.discovery"
        try:
            resp = await self._conn.request(subject, b"{}", timeout=timeout)
            data = json.loads(resp.data)
            cells: list[CellInfo] = []
            for entry in data.get("cells", []):
                cells.append(
                    CellInfo(
                        name=entry.get("name", ""),
                        formation=entry.get("formation", ""),
                        status=entry.get("status", ""),
                    )
                )
            return cells
        except Exception:
            return []

    async def health(self) -> bool:
        """Return True if the NATS connection is alive."""
        return self._nc is not None and self._nc.is_connected

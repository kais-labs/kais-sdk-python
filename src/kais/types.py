"""Core data types for the kAIs SDK."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Message:
    """A message exchanged between a client and a kAIs cell."""

    id: str
    from_: str
    to: str
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        from_: str,
        to: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Create a new message with auto-generated id and current timestamp."""
        return cls(
            id=uuid.uuid4().hex,
            from_=from_,
            to=to,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

    def to_json(self) -> bytes:
        """Serialize the message to JSON bytes for NATS publishing."""
        payload = {
            "id": self.id,
            "from": self.from_,
            "to": self.to,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        return json.dumps(payload).encode()

    @classmethod
    def from_json(cls, data: bytes | str) -> Message:
        """Deserialize a message from JSON bytes or string."""
        raw = json.loads(data)
        return cls(
            id=raw.get("id", ""),
            from_=raw.get("from", ""),
            to=raw.get("to", ""),
            content=raw.get("content", ""),
            timestamp=raw.get("timestamp", ""),
            metadata=raw.get("metadata", {}),
        )


@dataclass
class CellInfo:
    """Information about a discovered kAIs cell."""

    name: str
    formation: str
    status: str

"""Unit tests for kAIs SDK types (no NATS connection required)."""

from __future__ import annotations

import json

import pytest

from kais.types import Message, CellInfo


# ---------------------------------------------------------------------------
# Message.create
# ---------------------------------------------------------------------------

class TestMessageCreate:
    def test_create_sets_id_and_timestamp(self) -> None:
        msg = Message.create(from_="user:app", to="planner-0", content="hello")
        assert msg.id  # non-empty
        assert msg.timestamp  # non-empty
        assert msg.from_ == "user:app"
        assert msg.to == "planner-0"
        assert msg.content == "hello"
        assert msg.metadata == {}

    def test_create_with_metadata(self) -> None:
        meta = {"trace": "abc"}
        msg = Message.create(from_="u", to="c", content="x", metadata=meta)
        assert msg.metadata == {"trace": "abc"}

    def test_create_generates_unique_ids(self) -> None:
        a = Message.create(from_="u", to="c", content="1")
        b = Message.create(from_="u", to="c", content="2")
        assert a.id != b.id


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------

class TestMessageJson:
    def test_roundtrip(self) -> None:
        original = Message.create(from_="user:sdk", to="dev-0", content="ping")
        data = original.to_json()
        restored = Message.from_json(data)
        assert restored.id == original.id
        assert restored.from_ == original.from_
        assert restored.to == original.to
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.metadata == original.metadata

    def test_to_json_uses_from_key(self) -> None:
        """The JSON payload should use 'from' (not 'from_')."""
        msg = Message.create(from_="user:x", to="c", content="y")
        payload = json.loads(msg.to_json())
        assert "from" in payload
        assert "from_" not in payload

    def test_from_json_string(self) -> None:
        raw = '{"id":"1","from":"a","to":"b","content":"c","timestamp":"t"}'
        msg = Message.from_json(raw)
        assert msg.id == "1"
        assert msg.from_ == "a"

    def test_from_json_bytes(self) -> None:
        raw = b'{"id":"2","from":"x","to":"y","content":"z","timestamp":"t"}'
        msg = Message.from_json(raw)
        assert msg.id == "2"


# ---------------------------------------------------------------------------
# Missing / optional fields
# ---------------------------------------------------------------------------

class TestMessageMissingFields:
    def test_missing_metadata_defaults_to_empty(self) -> None:
        raw = '{"id":"1","from":"a","to":"b","content":"c","timestamp":"t"}'
        msg = Message.from_json(raw)
        assert msg.metadata == {}

    def test_missing_fields_default_to_empty_string(self) -> None:
        msg = Message.from_json("{}")
        assert msg.id == ""
        assert msg.from_ == ""
        assert msg.to == ""
        assert msg.content == ""
        assert msg.timestamp == ""
        assert msg.metadata == {}


# ---------------------------------------------------------------------------
# CellInfo
# ---------------------------------------------------------------------------

class TestCellInfo:
    def test_basic(self) -> None:
        info = CellInfo(name="dev-0", formation="my-form", status="running")
        assert info.name == "dev-0"
        assert info.formation == "my-form"
        assert info.status == "running"

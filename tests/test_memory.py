"""Tests for Memory Layer."""

import tempfile
from pathlib import Path

import pytest

from minions.memory import (
    AgentType,
    MemoryBroker,
    MemoryEvent,
    MemoryScope,
    MemoryType,
)


@pytest.fixture
def temp_memory_dir():
    """Create temporary memory directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def broker(temp_memory_dir):
    """Create Memory Broker with temp directory."""
    return MemoryBroker(base_dir=temp_memory_dir, enable_mem0=False)


class TestMemoryEvent:
    """Tests for MemoryEvent schema."""

    def test_create_event(self):
        event = MemoryEvent(
            content="Test memory",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
        )
        assert event.content == "Test memory"
        assert event.memory_type == MemoryType.PREFERENCE
        assert event.scope == MemoryScope.USER
        assert event.source_agent == AgentType.CLAUDE
        assert event.confidence == 1.0

    def test_to_dict(self):
        event = MemoryEvent(
            content="Test",
            memory_type=MemoryType.DECISION,
            scope=MemoryScope.PUBLIC,
            source_agent=AgentType.CODEX,
        )
        data = event.to_dict()
        assert data["content"] == "Test"
        assert data["memory_type"] == "decision"
        assert data["scope"] == "public"
        assert data["source_agent"] == "codex"

    def test_from_dict(self):
        data = {
            "id": "123",
            "content": "Test",
            "memory_type": "research",
            "scope": "agent",
            "source_agent": "gemini",
            "created_at": "2026-01-31T18:00:00",
        }
        event = MemoryEvent.from_dict(data)
        assert event.id == "123"
        assert event.content == "Test"
        assert event.memory_type == MemoryType.RESEARCH
        assert event.source_agent == AgentType.GEMINI


class TestMemoryBroker:
    """Tests for Memory Broker."""

    def test_add_memory(self, broker):
        event = broker.add(
            content="User prefers Japanese",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
        )
        assert event.content == "User prefers Japanese"
        assert event.id is not None

    def test_search_by_keyword(self, broker):
        broker.add(
            content="PRは日本語で書く",
            memory_type=MemoryType.PREFERENCE,
        )
        broker.add(
            content="コミットも日本語",
            memory_type=MemoryType.PREFERENCE,
        )
        broker.add(
            content="Use English for code",
            memory_type=MemoryType.PREFERENCE,
        )

        results = broker.search("日本語", use_semantic=False)
        assert len(results) == 2

    def test_search_by_agent(self, broker):
        broker.add(
            content="Codex decision",
            memory_type=MemoryType.DECISION,
            source_agent=AgentType.CODEX,
        )
        broker.add(
            content="Gemini research",
            memory_type=MemoryType.RESEARCH,
            source_agent=AgentType.GEMINI,
        )

        results = broker.search("", source_agent=AgentType.CODEX, use_semantic=False)
        assert len(results) == 1
        assert results[0].source_agent == AgentType.CODEX

    def test_redact_sensitive_data(self, broker):
        event = broker.add(
            content="API key is sk-1234567890abcdef1234567890abcdef1234567890abcdef",
            memory_type=MemoryType.OBSERVATION,
        )
        assert "[REDACTED]" in event.content
        assert "sk-" not in event.content

    def test_convenience_methods(self, broker):
        # Test preference
        pref = broker.remember_preference("Dark mode preferred")
        assert pref.memory_type == MemoryType.PREFERENCE

        # Test decision
        dec = broker.remember_decision("Use JWT for auth")
        assert dec.memory_type == MemoryType.DECISION
        assert dec.source_agent == AgentType.CODEX

        # Test research
        res = broker.remember_research("FastAPI is fast", topic="frameworks")
        assert res.memory_type == MemoryType.RESEARCH
        assert res.source_agent == AgentType.GEMINI

    def test_stats(self, broker):
        broker.add(content="Test 1", memory_type=MemoryType.PREFERENCE)
        broker.add(content="Test 2", memory_type=MemoryType.DECISION)

        stats = broker.get_stats()
        assert stats["total_events"] == 2
        assert stats["by_type"]["preference"] == 1
        assert stats["by_type"]["decision"] == 1

    def test_session_memory(self, broker):
        broker.start_session("test-session")

        broker.add(
            content="Session-specific memory",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.SESSION,
        )

        # Check session file was created
        session_file = broker.sessions_dir / "test-session.jsonl"
        assert session_file.exists()

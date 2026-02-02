"""
Memory Broker - Unified memory access layer for multi-agent system.

Responsibilities:
- Schema unification across agents
- Access control (scoping)
- Sensitive data redaction
- JSONL persistence (source of truth)
- mem0 vector indexing (semantic search)
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minions.memory.scoring import ScoringContext

from minions.memory.schema import (
    SENSITIVE_PATTERNS,
    AgentType,
    MemoryEvent,
    MemoryScope,
    MemoryType,
)


class MemoryBroker:
    """
    Central broker for memory operations.

    Manages both JSONL persistence and optional mem0 vector indexing.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        enable_mem0: bool = False,
        mem0_config: dict[str, Any] | None = None,
    ):
        """
        Initialize Memory Broker.

        Args:
            base_dir: Base directory for memory storage
            enable_mem0: Enable mem0 vector indexing
            mem0_config: Configuration for mem0 (LLM, embedder, vector store)
        """
        self.base_dir = base_dir or Path.home() / "minions" / ".claude" / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # JSONL files (source of truth)
        self.events_file = self.base_dir / "events.jsonl"
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)

        # Current session
        self._session_id: str | None = None

        # mem0 integration
        self._mem0 = None
        self._mem0_enabled = enable_mem0
        if enable_mem0:
            self._init_mem0(mem0_config)

    def _init_mem0(self, config: dict[str, Any] | None = None) -> None:
        """Initialize mem0 with configuration."""
        try:
            from mem0 import Memory

            if config is None:
                # Default config: use environment variables
                self._mem0 = Memory()
            else:
                self._mem0 = Memory.from_config(config)
            self._mem0_enabled = True
        except Exception as e:
            print(f"Warning: Failed to initialize mem0: {e}")
            self._mem0_enabled = False

    # =========================================================================
    # Session Management
    # =========================================================================

    def start_session(self, session_id: str | None = None) -> str:
        """Start or resume a session."""
        self._session_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        return self._session_id

    def get_session_id(self) -> str:
        """Get current session ID, creating one if needed."""
        if self._session_id is None:
            self._session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return self._session_id

    def _get_session_file(self) -> Path:
        """Get session-specific JSONL file."""
        return self.sessions_dir / f"{self.get_session_id()}.jsonl"

    # =========================================================================
    # Write Operations
    # =========================================================================

    def write(self, event: MemoryEvent) -> MemoryEvent:
        """
        Write a memory event.

        Flow: validate → redact → persist JSONL → index mem0 → return
        """
        # Validate
        self._validate(event)

        # Redact sensitive data
        event = self._redact(event)

        # Persist to JSONL
        self._persist_jsonl(event)

        # Index in mem0 (async-safe)
        if self._mem0_enabled and self._mem0:
            self._index_mem0(event)

        return event

    def add(
        self,
        content: str,
        memory_type: MemoryType | str,
        scope: MemoryScope | str = MemoryScope.USER,
        source_agent: AgentType | str = AgentType.CLAUDE,
        context: str = "",
        confidence: float = 1.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        scoring_context: "ScoringContext | None" = None,
    ) -> MemoryEvent:
        """
        Convenience method to add a memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            scope: Visibility scope
            source_agent: Agent that created this memory
            context: Additional context
            confidence: Confidence score (0-1)
            tags: Tags for categorization
            metadata: Additional metadata
            scoring_context: Optional context for importance scoring

        Returns:
            Created MemoryEvent
        """
        # Convert string enums if needed
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)
        if isinstance(scope, str):
            scope = MemoryScope(scope)
        if isinstance(source_agent, str):
            source_agent = AgentType(source_agent)

        # Prepare metadata with importance score
        final_metadata = metadata.copy() if metadata else {}

        # Calculate importance score if scoring context provided
        if scoring_context is not None:
            from minions.memory.scoring import (
                calculate_importance_score,
            )

            # Create temporary event for scoring
            temp_event = MemoryEvent(
                content=content,
                memory_type=memory_type,
                scope=scope,
                source_agent=source_agent,
                context=context,
                confidence=confidence,
                tags=tags or [],
                metadata=final_metadata,
            )
            importance = calculate_importance_score(temp_event, scoring_context)
            final_metadata["importance_score"] = importance

        event = MemoryEvent(
            content=content,
            memory_type=memory_type,
            scope=scope,
            source_agent=source_agent,
            context=context,
            confidence=confidence,
            tags=tags or [],
            metadata=final_metadata,
        )

        return self.write(event)

    def add_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: str,
        success: bool = True,
        execution_time_ms: int | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
    ) -> MemoryEvent:
        """
        Record a tool execution result with automatic importance scoring.

        Args:
            tool_name: Name of the tool (e.g., 'Bash', 'Edit', 'Read')
            tool_input: Tool input parameters
            result: Tool output/result summary
            success: Whether tool succeeded
            execution_time_ms: Execution time in milliseconds
            session_id: Current session ID
            task_id: Current task ID

        Returns:
            Created MemoryEvent with importance score
        """
        from minions.memory.scoring import ScoringContext

        # Create scoring context
        scoring_ctx = ScoringContext(
            tool_name=tool_name,
            tool_success=success,
            execution_time_ms=execution_time_ms,
            session_id=session_id,
            task_id=task_id,
        )

        # Build content
        content = f"Tool: {tool_name}\nResult: {result}"
        if not success:
            content = f"[FAILURE] {content}"

        # Build metadata
        metadata = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "outcome": "success" if success else "failure",
            "execution_time_ms": execution_time_ms,
        }
        if session_id:
            metadata["session_id"] = session_id
        if task_id:
            metadata["task_id"] = task_id

        return self.add(
            content=content,
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.SESSION,
            source_agent=AgentType.CLAUDE,
            context=f"tool:{tool_name}",
            metadata=metadata,
            scoring_context=scoring_ctx,
        )

    def _validate(self, event: MemoryEvent) -> None:
        """Validate memory event."""
        if not event.content:
            raise ValueError("Memory content cannot be empty")
        if event.confidence < 0 or event.confidence > 1:
            raise ValueError("Confidence must be between 0 and 1")

    def _redact(self, event: MemoryEvent) -> MemoryEvent:
        """Redact sensitive data from memory content."""
        content = event.content
        for pattern in SENSITIVE_PATTERNS:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)

        # Create new event with redacted content
        if content != event.content:
            return MemoryEvent(
                id=event.id,
                content=content,
                memory_type=event.memory_type,
                scope=event.scope,
                source_agent=event.source_agent,
                context=event.context,
                confidence=event.confidence,
                ttl_days=event.ttl_days,
                tags=event.tags,
                metadata={**event.metadata, "_redacted": True},
                created_at=event.created_at,
            )
        return event

    def _persist_jsonl(self, event: MemoryEvent) -> None:
        """Persist event to JSONL file."""
        # Session-scoped events go to session file
        if event.scope == MemoryScope.SESSION:
            target_file = self._get_session_file()
        else:
            target_file = self.events_file

        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def _index_mem0(self, event: MemoryEvent) -> None:
        """Index event in mem0 for semantic search."""
        if not self._mem0:
            return

        try:
            # Determine mem0 scope
            user_id = "default"
            agent_id = event.source_agent.value

            self._mem0.add(
                event.content,
                user_id=user_id,
                agent_id=agent_id,
                metadata={
                    "event_id": event.id,
                    "memory_type": event.memory_type.value,
                    "scope": event.scope.value,
                    "context": event.context,
                    "tags": event.tags,
                },
            )
        except Exception as e:
            # Don't fail write if mem0 indexing fails
            print(f"Warning: mem0 indexing failed: {e}")

    # =========================================================================
    # Read Operations
    # =========================================================================

    def search(
        self,
        query: str,
        scope: MemoryScope | str | None = None,
        source_agent: AgentType | str | None = None,
        memory_type: MemoryType | str | None = None,
        limit: int = 10,
        use_semantic: bool = True,
    ) -> list[MemoryEvent]:
        """
        Search memories.

        Uses both exact match (JSONL) and semantic search (mem0) if available.

        Args:
            query: Search query
            scope: Filter by scope
            source_agent: Filter by agent
            memory_type: Filter by type
            limit: Maximum results
            use_semantic: Use mem0 semantic search if available

        Returns:
            List of matching MemoryEvents
        """
        results: list[MemoryEvent] = []

        # Semantic search with mem0
        if use_semantic and self._mem0_enabled and self._mem0:
            try:
                mem0_results = self._mem0.search(query, limit=limit)
                for m in mem0_results:
                    # Retrieve full event from JSONL by ID
                    event_id = m.get("metadata", {}).get("event_id")
                    if event_id:
                        event = self._get_by_id(event_id)
                        if event:
                            results.append(event)
            except Exception as e:
                print(f"Warning: mem0 search failed: {e}")

        # Exact search in JSONL (keyword match)
        jsonl_results = self._search_jsonl(
            query=query,
            scope=scope,
            source_agent=source_agent,
            memory_type=memory_type,
            limit=limit,
        )

        # Merge and dedupe
        seen_ids = {r.id for r in results}
        for event in jsonl_results:
            if event.id not in seen_ids:
                results.append(event)
                seen_ids.add(event.id)

        # Sort by recency
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results[:limit]

    def _search_jsonl(
        self,
        query: str,
        scope: MemoryScope | str | None = None,
        source_agent: AgentType | str | None = None,
        memory_type: MemoryType | str | None = None,
        limit: int = 10,
    ) -> list[MemoryEvent]:
        """Search JSONL files with keyword matching."""
        # Convert string enums
        if isinstance(scope, str):
            scope = MemoryScope(scope)
        if isinstance(source_agent, str):
            source_agent = AgentType(source_agent)
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        results: list[MemoryEvent] = []
        query_lower = query.lower()

        # Search main events file
        for event in self._load_jsonl(self.events_file):
            if self._matches(event, query_lower, scope, source_agent, memory_type):
                results.append(event)

        # Search session files if scope is SESSION
        if scope is None or scope == MemoryScope.SESSION:
            for session_file in self.sessions_dir.glob("*.jsonl"):
                for event in self._load_jsonl(session_file):
                    if self._matches(
                        event, query_lower, scope, source_agent, memory_type
                    ):
                        results.append(event)

        # Sort by recency
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results[:limit]

    def _matches(
        self,
        event: MemoryEvent,
        query_lower: str,
        scope: MemoryScope | None,
        source_agent: AgentType | None,
        memory_type: MemoryType | None,
    ) -> bool:
        """Check if event matches filters."""
        # Keyword match
        if query_lower and query_lower not in event.content.lower():
            if query_lower not in event.context.lower():
                return False

        # Scope filter
        if scope and event.scope != scope:
            return False

        # Agent filter
        if source_agent and event.source_agent != source_agent:
            return False

        # Type filter
        if memory_type and event.memory_type != memory_type:
            return False

        return True

    def _load_jsonl(self, path: Path) -> list[MemoryEvent]:
        """Load events from JSONL file."""
        if not path.exists():
            return []

        events = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        events.append(MemoryEvent.from_dict(data))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        return events

    def _get_by_id(self, event_id: str) -> MemoryEvent | None:
        """Get event by ID from JSONL files."""
        # Search main file
        for event in self._load_jsonl(self.events_file):
            if event.id == event_id:
                return event

        # Search session files
        for session_file in self.sessions_dir.glob("*.jsonl"):
            for event in self._load_jsonl(session_file):
                if event.id == event_id:
                    return event

        return None

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def remember_preference(self, preference: str, context: str = "") -> MemoryEvent:
        """Record user preference."""
        return self.add(
            content=preference,
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
            context=context,
        )

    def remember_decision(
        self,
        decision: str,
        agent: AgentType = AgentType.CODEX,
        context: str = "",
    ) -> MemoryEvent:
        """Record design decision."""
        return self.add(
            content=decision,
            memory_type=MemoryType.DECISION,
            scope=MemoryScope.PUBLIC,
            source_agent=agent,
            context=context,
        )

    def remember_research(
        self,
        finding: str,
        topic: str = "",
    ) -> MemoryEvent:
        """Record research finding from Gemini."""
        return self.add(
            content=finding,
            memory_type=MemoryType.RESEARCH,
            scope=MemoryScope.PUBLIC,
            source_agent=AgentType.GEMINI,
            context=topic,
        )

    def remember_error(self, error: str, solution: str) -> MemoryEvent:
        """Record error pattern and solution."""
        return self.add(
            content=f"Error: {error}\nSolution: {solution}",
            memory_type=MemoryType.ERROR,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
            metadata={"error": error, "solution": solution},
        )

    def remember_workflow(self, workflow: str, trigger: str = "") -> MemoryEvent:
        """Record workflow pattern."""
        return self.add(
            content=workflow,
            memory_type=MemoryType.WORKFLOW,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
            context=trigger,
        )

    # =========================================================================
    # Statistics and Maintenance
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        events = self._load_jsonl(self.events_file)

        # Count session files
        session_files = list(self.sessions_dir.glob("*.jsonl"))
        session_events = sum(len(self._load_jsonl(f)) for f in session_files)

        # Count by type
        by_type = {}
        by_agent = {}
        by_scope = {}

        for event in events:
            by_type[event.memory_type.value] = (
                by_type.get(event.memory_type.value, 0) + 1
            )
            by_agent[event.source_agent.value] = (
                by_agent.get(event.source_agent.value, 0) + 1
            )
            by_scope[event.scope.value] = by_scope.get(event.scope.value, 0) + 1

        return {
            "total_events": len(events),
            "session_events": session_events,
            "session_count": len(session_files),
            "by_type": by_type,
            "by_agent": by_agent,
            "by_scope": by_scope,
            "mem0_enabled": self._mem0_enabled,
        }

    def cleanup_expired(self) -> int:
        """Remove expired memories based on TTL."""
        events = self._load_jsonl(self.events_file)
        now = datetime.now()
        kept = []
        removed = 0

        for event in events:
            if event.ttl_days is not None:
                created = datetime.fromisoformat(event.created_at)
                if now - created > timedelta(days=event.ttl_days):
                    removed += 1
                    continue
            kept.append(event)

        # Rewrite file
        if removed > 0:
            with open(self.events_file, "w", encoding="utf-8") as f:
                for event in kept:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        return removed


# Global broker instance
_broker: MemoryBroker | None = None


def get_broker(enable_mem0: bool | None = None) -> MemoryBroker:
    """
    Get or create global Memory Broker instance.

    Args:
        enable_mem0: Enable mem0 vector search. If None, auto-detect based on
                     OPENAI_API_KEY environment variable.

    Returns:
        MemoryBroker instance
    """
    global _broker
    if _broker is None:
        import os

        from minions.memory.embeddings import get_mem0_config

        # Auto-enable mem0 if OPENAI_API_KEY is set
        if enable_mem0 is None:
            enable_mem0 = bool(os.environ.get("OPENAI_API_KEY"))

        mem0_config = None
        if enable_mem0:
            mem0_config = get_mem0_config(
                embedding_provider="openai",
                llm_provider="openai",
            )

        _broker = MemoryBroker(enable_mem0=enable_mem0, mem0_config=mem0_config)
    return _broker

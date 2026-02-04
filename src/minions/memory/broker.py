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
    AgentType,
    MemoryEvent,
    MemoryScope,
    MemoryType,
)

# Default scope mapping by memory type
DEFAULT_SCOPE_BY_TYPE: dict[str, MemoryScope] = {
    "preference": MemoryScope.USER,  # User preferences -> Global
    "workflow": MemoryScope.PROJECT,  # Workflow patterns -> Project-specific
    "decision": MemoryScope.PROJECT,  # Design decisions -> Project-specific
    "error": MemoryScope.PROJECT,  # Error solutions -> Project-specific
    "observation": MemoryScope.SESSION,  # Observations -> Session temporary
    "plan": MemoryScope.PROJECT,  # Plans -> Project-specific
    "artifact": MemoryScope.PROJECT,  # Artifacts -> Project-specific
    "research": MemoryScope.PUBLIC,  # Research -> Global public
}


class PromotionRule:
    """Memory promotion rules for tier transitions."""

    @staticmethod
    def should_promote_to_project(event: MemoryEvent, stats: dict[str, Any]) -> bool:
        """
        Check if session memory should be promoted to project scope.

        Conditions:
        - Reused 2+ times
        - Success rate >= 80%
        - Explicitly marked important by user

        Args:
            event: Memory event to check
            stats: Statistics dict with reuse_count, success_rate, etc.

        Returns:
            True if should promote
        """
        # Condition 1: Reuse count
        if stats.get("reuse_count", 0) >= 2:
            return True

        # Condition 2: High success rate
        if stats.get("success_rate", 0) >= 0.8:
            return True

        # Condition 3: User explicit marking
        if "explicit" in event.tags or "important" in event.tags:
            return True

        return False

    @staticmethod
    def should_promote_to_global(event: MemoryEvent, stats: dict[str, Any]) -> bool:
        """
        Check if project memory should be promoted to global scope.

        Conditions:
        - Successfully used across 2+ projects
        - User preference type (always global)

        Args:
            event: Memory event to check
            stats: Statistics dict with cross_project_success, etc.

        Returns:
            True if should promote
        """
        # Condition 1: Cross-project success
        if stats.get("cross_project_success", 0) >= 2:
            return True

        # Condition 2: User preference (always promote)
        if event.memory_type == MemoryType.PREFERENCE:
            return True

        return False


class MemoryBroker:
    """
    Central broker for memory operations.

    Manages both JSONL persistence and optional mem0 vector indexing.
    """

    @staticmethod
    def _get_default_memory_dir() -> Path:
        """
        Get default global memory directory.

        Priority:
        1. AI_MEMORY_PATH environment variable (if set, use parent directory)
        2. ~/.config/ai/memory (macOS/Linux standard)

        Returns:
            Path: Global memory directory path
        """
        import os

        # Priority 1: Allow override via environment variable
        if custom_path := os.environ.get("AI_MEMORY_PATH"):
            # If AI_MEMORY_PATH points to events.jsonl, use parent directory
            custom = Path(custom_path)
            if custom.name == "events.jsonl":
                return custom.parent
            return custom

        # Priority 2: Use OS config directory
        config_home = Path.home() / ".config"
        return config_home / "ai" / "memory"

    @staticmethod
    def _get_memory_paths() -> dict[str, Path]:
        """
        Get memory paths for all scopes.

        Returns:
            Dict with keys: 'global', 'project', 'session'
        """
        # Global memory (cross-project, user-wide)
        global_path = MemoryBroker._get_default_memory_dir()

        # Project memory (current project)
        project_root = Path.cwd()
        while project_root != project_root.parent:
            if (project_root / ".git").exists() or (project_root / ".claude").exists():
                break
            project_root = project_root.parent
        else:
            # No git/claude root found, use cwd
            project_root = Path.cwd()

        project_path = project_root / ".claude" / "memory"

        # Session memory (temporary, inside project)
        session_path = project_path / "sessions"

        return {
            "global": global_path,
            "project": project_path,
            "session": session_path,
        }

    def __init__(
        self,
        base_dir: Path | None = None,
        enable_mem0: bool = False,
        mem0_config: dict[str, Any] | None = None,
    ):
        """
        Initialize Memory Broker.

        Args:
            base_dir: Base directory for global memory storage (legacy, use paths instead)
            enable_mem0: Enable mem0 vector indexing
            mem0_config: Configuration for mem0 (LLM, embedder, vector store)
        """
        # Get all memory paths (3-tier architecture)
        paths = self._get_memory_paths()
        self.global_dir = paths["global"]
        self.project_dir = paths["project"]
        self.sessions_dir = paths["session"]

        # Create directories
        self.global_dir.mkdir(parents=True, exist_ok=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Legacy: base_dir override (for backward compatibility)
        if base_dir:
            self.global_dir = base_dir
            self.global_dir.mkdir(parents=True, exist_ok=True)

        # JSONL files (source of truth)
        # Note: scope-specific files are determined by _get_storage_path()
        self.events_file = self.global_dir / "events.jsonl"  # Legacy global file

        # Current session
        self._session_id: str | None = None

        # ID cache for N+1 query mitigation
        self._id_cache: dict[str, MemoryEvent] = {}

        # File lock for thread-safe writes
        import threading

        self._file_lock = threading.Lock()

        # Redaction patterns (compiled once)
        self._redaction_patterns = self._compile_redaction_patterns()

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
    # Sensitive Data Redaction
    # =========================================================================

    def _compile_redaction_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Compile redaction patterns for sensitive data."""
        patterns = [
            # API Keys (OpenAI, Anthropic, etc.)
            (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "[REDACTED_API_KEY]"),
            (re.compile(r"sk-proj-[a-zA-Z0-9_-]{32,}"), "[REDACTED_API_KEY]"),
            # AWS
            (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
            (
                re.compile(r"[a-zA-Z0-9/+=]{40}(?=\s|$)"),
                "[REDACTED_AWS_SECRET]",
            ),
            # GitHub tokens (flexible length)
            (re.compile(r"ghp_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
            (re.compile(r"gho_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
            (re.compile(r"ghs_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
            # Bearer tokens
            (re.compile(r"Bearer\s+[a-zA-Z0-9\-._~+/]+"), "[REDACTED_BEARER_TOKEN]"),
            # Generic secrets (key=value or key:value patterns)
            (
                re.compile(
                    r"(api[_-]?key|apikey|secret|password|token)\s*[=:]\s*['\"]?([^\s'\"]+)",
                    re.IGNORECASE,
                ),
                r"\1=[REDACTED]",
            ),
            # JWT tokens
            (
                re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
                "[REDACTED_JWT]",
            ),
            # Private keys
            (
                re.compile(
                    r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----.*?-----END \1PRIVATE KEY-----",
                    re.DOTALL,
                ),
                "[REDACTED_PRIVATE_KEY]",
            ),
        ]
        return patterns

    def _apply_redaction_patterns(self, text: str) -> str:
        """Apply redaction patterns to text."""
        if not text:
            return text

        result = text
        for pattern, replacement in self._redaction_patterns:
            result = pattern.sub(replacement, result)
        return result

    def _redact_recursive(self, obj: Any) -> Any:
        """Recursively redact sensitive data from any object."""
        if isinstance(obj, str):
            # String: apply redaction patterns
            return self._apply_redaction_patterns(obj)

        elif isinstance(obj, dict):
            # Dict: recursively redact each value
            return {key: self._redact_recursive(value) for key, value in obj.items()}

        elif isinstance(obj, list):
            # List: recursively redact each item
            return [self._redact_recursive(item) for item in obj]

        elif isinstance(obj, tuple):
            # Tuple: recursively redact each item
            return tuple(self._redact_recursive(item) for item in obj)

        else:
            # Other types (int, bool, None, etc.): return as-is
            return obj

    def _redact_sensitive_data(self, event: MemoryEvent) -> MemoryEvent:
        """Redact sensitive data from both content and metadata (recursive)."""
        # Redact content
        event.content = self._apply_redaction_patterns(event.content)

        # Redact metadata (recursive)
        if event.metadata:
            event.metadata = self._redact_recursive(event.metadata)

        return event

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

    def _get_storage_path(self, scope: MemoryScope) -> Path:
        """
        Get storage path based on memory scope.

        Args:
            scope: Memory scope

        Returns:
            Path to JSONL file for this scope
        """
        if scope == MemoryScope.SESSION:
            return self._get_session_file()
        elif scope == MemoryScope.PROJECT:
            return self.project_dir / "events.jsonl"
        else:  # USER, AGENT, PUBLIC -> Global
            return self.global_dir / "events.jsonl"

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
        event = self._redact_sensitive_data(event)

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
        scope: MemoryScope | str | None = None,
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
            scope: Visibility scope (if None, use default based on memory_type)
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

        # Auto-select scope if not provided
        if scope is None:
            scope = DEFAULT_SCOPE_BY_TYPE.get(memory_type.value, MemoryScope.USER)
        elif isinstance(scope, str):
            scope = MemoryScope(scope)

        if isinstance(source_agent, str):
            source_agent = AgentType(source_agent)

        # Prepare metadata with importance score
        final_metadata = metadata.copy() if metadata else {}

        # Calculate importance score (always calculate, even without context)
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

    def _persist_jsonl(self, event: MemoryEvent) -> None:
        """Persist event to JSONL file with thread-safe locking."""
        # Get target file based on scope
        target_file = self._get_storage_path(event.scope)

        # Ensure parent directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Thread lock for same-process concurrency
        with self._file_lock:
            with open(target_file, "a", encoding="utf-8") as f:
                # File lock for multi-process concurrency (Unix only)
                try:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except (ImportError, AttributeError):
                    # Windows or unsupported platform - thread lock is sufficient
                    pass

                try:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                    f.flush()
                finally:
                    # Release file lock if acquired
                    try:
                        import fcntl

                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (ImportError, AttributeError):
                        pass

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

        # Convert string enums if needed
        if isinstance(scope, str):
            scope = MemoryScope(scope)
        if isinstance(source_agent, str):
            source_agent = AgentType(source_agent)
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        # Semantic search with mem0
        if use_semantic and self._mem0_enabled and self._mem0:
            try:
                mem0_results = self._mem0.search(query, limit=limit)
                for m in mem0_results:
                    # Retrieve full event from JSONL by ID
                    event_id = m.get("metadata", {}).get("event_id")
                    if event_id:
                        event = self._get_by_id(event_id, scope_hint=scope)
                        if event:
                            # Apply filters (CRITICAL: prevent scope leakage)
                            if scope and event.scope != scope:
                                continue
                            if source_agent and event.source_agent != source_agent:
                                continue
                            if memory_type and event.memory_type != memory_type:
                                continue
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

    def search_with_budget(
        self,
        query: str,
        token_budget: int = 10000,
        scope_weights: dict[str, float] | None = None,
    ) -> list[MemoryEvent]:
        """
        Search with token budget across scopes with weighted allocation.

        Args:
            query: Search query
            token_budget: Total token budget for results
            scope_weights: Weight allocation per scope (session, project, user)
                          Defaults to {session: 0.4, project: 0.4, user: 0.2}

        Returns:
            List of MemoryEvents within budget
        """
        if scope_weights is None:
            scope_weights = {
                "session": 0.4,
                "project": 0.4,
                "user": 0.2,
            }

        results: list[MemoryEvent] = []

        # Estimate ~100 tokens per event (rough average)
        tokens_per_event = 100

        # Session memories (weighted allocation)
        session_limit = int(
            token_budget * scope_weights.get("session", 0.4) / tokens_per_event
        )
        if session_limit > 0:
            session_results = self.search(
                query,
                scope=MemoryScope.SESSION,
                limit=session_limit,
                use_semantic=False,
            )
            results.extend(session_results)

        # Project memories (weighted allocation)
        project_limit = int(
            token_budget * scope_weights.get("project", 0.4) / tokens_per_event
        )
        if project_limit > 0:
            project_results = self.search(
                query,
                scope=MemoryScope.PROJECT,
                limit=project_limit,
                use_semantic=False,
            )
            results.extend(project_results)

        # User/Global memories (weighted allocation)
        user_limit = int(
            token_budget * scope_weights.get("user", 0.2) / tokens_per_event
        )
        if user_limit > 0:
            user_results = self.search(
                query, scope=MemoryScope.USER, limit=user_limit, use_semantic=False
            )
            results.extend(user_results)

        # Deduplicate and sort by importance
        seen_ids = set()
        unique_results = []
        for event in results:
            if event.id not in seen_ids:
                unique_results.append(event)
                seen_ids.add(event.id)

        # Sort by importance score (descending)
        unique_results.sort(
            key=lambda e: e.metadata.get("importance_score", 0.5), reverse=True
        )

        return unique_results

    def _search_jsonl(
        self,
        query: str,
        scope: MemoryScope | str | None = None,
        source_agent: AgentType | str | None = None,
        memory_type: MemoryType | str | None = None,
        limit: int = 10,
    ) -> list[MemoryEvent]:
        """Search JSONL files with keyword matching across all scopes."""
        # Convert string enums
        if isinstance(scope, str):
            scope = MemoryScope(scope)
        if isinstance(source_agent, str):
            source_agent = AgentType(source_agent)
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        results: list[MemoryEvent] = []
        query_lower = query.lower()

        # Search based on scope filter
        if scope is None:
            # Search all scopes (but only current session for SESSION scope)
            files_to_search = [
                self.global_dir / "events.jsonl",  # Global (USER, AGENT, PUBLIC)
                self.project_dir / "events.jsonl",  # Project
            ]
            # Add current session file only (prevent cross-session leakage)
            session_id = self.get_session_id()
            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if session_file.exists():
                files_to_search.append(session_file)
        elif scope == MemoryScope.SESSION:
            # Search current session file only
            session_id = self.get_session_id()
            session_file = self.sessions_dir / f"{session_id}.jsonl"
            files_to_search = [session_file] if session_file.exists() else []
        elif scope == MemoryScope.PROJECT:
            # Search project file only
            files_to_search = [self.project_dir / "events.jsonl"]
        else:  # USER, AGENT, PUBLIC
            # Search global file only
            files_to_search = [self.global_dir / "events.jsonl"]

        # Search all target files
        for file_path in files_to_search:
            for event in self._load_jsonl(file_path):
                if self._matches(event, query_lower, scope, source_agent, memory_type):
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

    def _get_by_id(
        self, event_id: str, scope_hint: MemoryScope | None = None
    ) -> MemoryEvent | None:
        """
        Get event by ID from JSONL files.

        Uses simple cache to mitigate N+1 queries during search.
        TODO: Add proper indexing (e.g., SQLite) for better performance.

        Args:
            event_id: Event ID to find
            scope_hint: Optional scope hint to narrow search (performance optimization)
        """
        # Check cache first
        if event_id in self._id_cache:
            return self._id_cache[event_id]

        # Determine files to search based on scope hint
        files_to_search: list[Path] = []

        if scope_hint == MemoryScope.SESSION:
            # Search current session file only
            session_id = self.get_session_id()
            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if session_file.exists():
                files_to_search.append(session_file)
        elif scope_hint == MemoryScope.PROJECT:
            # Search project file only
            files_to_search.append(self.project_dir / "events.jsonl")
        elif scope_hint in (MemoryScope.USER, MemoryScope.AGENT, MemoryScope.PUBLIC):
            # Search global file only
            files_to_search.append(self.global_dir / "events.jsonl")
        else:
            # No hint or ALL: search all files
            files_to_search.extend(
                [
                    self.global_dir / "events.jsonl",
                    self.project_dir / "events.jsonl",
                ]
            )
            if self.sessions_dir.exists():
                # Without scope hint, we must search current session only to prevent leakage
                session_id = self.get_session_id()
                session_file = self.sessions_dir / f"{session_id}.jsonl"
                if session_file.exists():
                    files_to_search.append(session_file)

        for file_path in files_to_search:
            for event in self._load_jsonl(file_path):
                # Populate cache while searching
                self._id_cache[event.id] = event
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
        scope: MemoryScope = MemoryScope.PROJECT,
    ) -> MemoryEvent:
        """Record design decision."""
        return self.add(
            content=decision,
            memory_type=MemoryType.DECISION,
            scope=scope,
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

    def remember_error(
        self,
        error: str,
        solution: str,
        scope: MemoryScope = MemoryScope.PROJECT,
    ) -> MemoryEvent:
        """Record error pattern and solution."""
        return self.add(
            content=f"Error: {error}\nSolution: {solution}",
            memory_type=MemoryType.ERROR,
            scope=scope,
            source_agent=AgentType.CLAUDE,
            metadata={"error": error, "solution": solution},
        )

    def remember_workflow(
        self,
        workflow: str,
        trigger: str = "",
        scope: MemoryScope = MemoryScope.PROJECT,
    ) -> MemoryEvent:
        """Record workflow pattern."""
        return self.add(
            content=workflow,
            memory_type=MemoryType.WORKFLOW,
            scope=scope,
            source_agent=AgentType.CLAUDE,
            context=trigger,
        )

    # =========================================================================
    # Statistics and Maintenance
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics across all scopes."""
        # Load events from all scopes
        global_events = self._load_jsonl(self.global_dir / "events.jsonl")
        project_events = self._load_jsonl(self.project_dir / "events.jsonl")

        # Count session files and events
        session_files = (
            list(self.sessions_dir.glob("*.jsonl"))
            if self.sessions_dir.exists()
            else []
        )
        session_events_list = []
        for f in session_files:
            session_events_list.extend(self._load_jsonl(f))

        # Combine all events for statistics
        all_events = global_events + project_events + session_events_list

        # Count by type, agent, scope
        by_type = {}
        by_agent = {}
        by_scope = {}

        for event in all_events:
            by_type[event.memory_type.value] = (
                by_type.get(event.memory_type.value, 0) + 1
            )
            by_agent[event.source_agent.value] = (
                by_agent.get(event.source_agent.value, 0) + 1
            )
            by_scope[event.scope.value] = by_scope.get(event.scope.value, 0) + 1

        return {
            "total_events": len(all_events),
            "global_events": len(global_events),
            "project_events": len(project_events),
            "session_events": len(session_events_list),
            "session_count": len(session_files),
            "by_type": by_type,
            "by_agent": by_agent,
            "by_scope": by_scope,
            "mem0_enabled": self._mem0_enabled,
        }

    def cleanup_expired(self) -> int:
        """Remove expired memories based on TTL across all scopes (thread-safe)."""
        total_removed = 0

        # Process global and project files
        scope_files = [
            self.global_dir / "events.jsonl",
            self.project_dir / "events.jsonl",
        ]

        for file_path in scope_files:
            if file_path.exists():
                total_removed += self._cleanup_file_with_lock(file_path)

        # Process all session files
        if self.sessions_dir.exists():
            for session_file in self.sessions_dir.glob("*.jsonl"):
                total_removed += self._cleanup_file_with_lock(session_file)

        return total_removed

    def _cleanup_file_with_lock(self, file_path: Path) -> int:
        """
        Cleanup a single file with proper file locking.

        Uses temporary file and atomic replacement to avoid data loss.

        Args:
            file_path: Path to the JSONL file to clean up

        Returns:
            Number of removed events
        """
        import fcntl

        temp_file = file_path.with_suffix(".cleaning")
        removed_count = 0
        now = datetime.now()

        try:
            with self._file_lock:
                # Read and filter with exclusive lock
                with open(file_path, "r+", encoding="utf-8") as f_in:
                    # Acquire exclusive lock
                    fcntl.flock(f_in.fileno(), fcntl.LOCK_EX)

                    try:
                        # Write non-expired events to temp file
                        with open(temp_file, "w", encoding="utf-8") as f_out:
                            for line in f_in:
                                line = line.strip()
                                if not line:
                                    continue

                                try:
                                    event_dict = json.loads(line)
                                    event = MemoryEvent.from_dict(event_dict)

                                    # Check if expired
                                    if event.ttl_days is not None:
                                        created = datetime.fromisoformat(
                                            event.created_at
                                        )
                                        if now - created > timedelta(
                                            days=event.ttl_days
                                        ):
                                            removed_count += 1
                                            continue

                                    # Keep this event
                                    f_out.write(line + "\n")

                                except (json.JSONDecodeError, KeyError, ValueError):
                                    # Keep malformed lines to avoid data loss
                                    f_out.write(line + "\n")

                        # Atomically replace original file
                        temp_file.replace(file_path)

                    finally:
                        fcntl.flock(f_in.fileno(), fcntl.LOCK_UN)

        finally:
            # Cleanup temp file if it still exists
            temp_file.unlink(missing_ok=True)

        return removed_count

    # =========================================================================
    # Memory Promotion
    # =========================================================================

    def _get_memory_stats(self, event_id: str) -> dict[str, Any]:
        """
        Get statistics for a memory event.

        TODO: Implement proper tracking (e.g., usage counter, success tracking)
        For now, returns basic stats from metadata.

        Args:
            event_id: Event ID

        Returns:
            Statistics dict
        """
        event = self._get_by_id(event_id)
        if not event:
            return {}

        # Extract stats from metadata (if tracked)
        return {
            "reuse_count": event.metadata.get("reuse_count", 0),
            "success_rate": event.metadata.get("success_rate", 0),
            "cross_project_success": event.metadata.get("cross_project_success", 0),
        }

    def _promote_memory(self, event: MemoryEvent, target_scope: MemoryScope) -> bool:
        """
        Promote a memory to a higher scope.

        Args:
            event: Event to promote
            target_scope: Target scope (PROJECT or USER/PUBLIC)

        Returns:
            True if successful
        """
        # Update scope
        promoted_event = MemoryEvent(
            id=event.id,
            content=event.content,
            memory_type=event.memory_type,
            scope=target_scope,
            source_agent=event.source_agent,
            context=event.context,
            confidence=event.confidence,
            ttl_days=event.ttl_days,
            tags=event.tags + ["promoted"],  # Add promotion tag
            metadata={**event.metadata, "promoted_at": datetime.now().isoformat()},
            created_at=event.created_at,
        )

        # Write to new scope
        self._persist_jsonl(promoted_event)

        return True

    def promote_memories(self) -> dict[str, int]:
        """
        Promote memories based on promotion rules.

        Returns:
            Dict with promotion counts
        """
        session_to_project = 0
        project_to_global = 0

        # Session -> Project
        if self.sessions_dir.exists():
            for session_file in self.sessions_dir.glob("*.jsonl"):
                session_memories = self._load_jsonl(session_file)
                for memory in session_memories:
                    if memory.scope != MemoryScope.SESSION:
                        continue
                    stats = self._get_memory_stats(memory.id)
                    if PromotionRule.should_promote_to_project(memory, stats):
                        self._promote_memory(memory, MemoryScope.PROJECT)
                        session_to_project += 1

        # Project -> Global
        project_file = self.project_dir / "events.jsonl"
        if project_file.exists():
            project_memories = self._load_jsonl(project_file)
            for memory in project_memories:
                if memory.scope != MemoryScope.PROJECT:
                    continue
                stats = self._get_memory_stats(memory.id)
                if PromotionRule.should_promote_to_global(memory, stats):
                    # Promote to USER or PUBLIC based on type
                    target_scope = (
                        MemoryScope.PUBLIC
                        if memory.memory_type == MemoryType.RESEARCH
                        else MemoryScope.USER
                    )
                    self._promote_memory(memory, target_scope)
                    project_to_global += 1

        return {
            "session_to_project": session_to_project,
            "project_to_global": project_to_global,
        }


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

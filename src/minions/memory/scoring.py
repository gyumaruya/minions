"""
Scoring Engine - Importance and relevance scoring for memory events.

Provides two main scoring functions:
1. Importance scoring: Calculate how important a memory is for storage
2. Recall scoring: Calculate how relevant a memory is for retrieval

Based on the self-improvement memory cycle design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minions.memory.schema import MemoryEvent


class OutcomeType(str, Enum):
    """Outcome types for tool executions."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class ImportanceWeights:
    """Weights for importance score calculation.

    Formula:
        Score = outcome×0.25 + reuse×0.20 + cross_impact×0.20
              + novelty×0.15 + user_signal×0.15 + cost_reduction×0.05
    """

    outcome: float = 0.25
    reuse: float = 0.20
    cross_impact: float = 0.20
    novelty: float = 0.15
    user_signal: float = 0.15
    cost_reduction: float = 0.05


@dataclass
class RecallWeights:
    """Weights for recall score calculation.

    Formula:
        Score = importance×0.4 + recency×0.3 + role_fit×0.2 + outcome×0.1
    """

    importance: float = 0.4
    recency: float = 0.3
    role_fit: float = 0.2
    outcome: float = 0.1


# Default weights
DEFAULT_IMPORTANCE_WEIGHTS = ImportanceWeights()
DEFAULT_RECALL_WEIGHTS = RecallWeights()


@dataclass
class ScoringContext:
    """Context for scoring a memory event.

    Provides information about the current state and environment
    for accurate importance/recall scoring.
    """

    # Tool execution context
    tool_name: str | None = None
    tool_success: bool = True
    execution_time_ms: int | None = None

    # Session context
    session_id: str | None = None
    task_id: str | None = None
    agent_role: str | None = None

    # User interaction
    user_signal: float = 0.0  # -1.0 to 1.0 (negative = bad, positive = good)

    # Memory statistics (for novelty calculation)
    similar_memory_count: int = 0
    total_memory_count: int = 0

    # Historical data
    past_success_rate: float | None = None  # For this pattern
    past_reuse_count: int = 0

    # Additional context
    metadata: dict[str, Any] | None = None


# Memory type base weights for importance scoring
# These represent inherent importance of each memory type
MEMORY_TYPE_BASE_WEIGHTS = {
    "preference": 0.9,  # High - Directly impacts behavior
    "workflow": 0.8,  # High - Repeated patterns
    "decision": 0.85,  # High - Architecture choices
    "error": 0.7,  # Medium - Context-dependent learning
    "observation": 0.5,  # Low - Routine actions
    "research": 0.75,  # Medium-High - Investigation results
    "plan": 0.8,  # High - Strategic planning
    "artifact": 0.7,  # Medium - Concrete outputs
}


class ScoringEngine:
    """Engine for calculating importance and recall scores."""

    def __init__(
        self,
        importance_weights: ImportanceWeights | None = None,
        recall_weights: RecallWeights | None = None,
    ):
        """Initialize scoring engine with optional custom weights."""
        self.importance_weights = importance_weights or DEFAULT_IMPORTANCE_WEIGHTS
        self.recall_weights = recall_weights or DEFAULT_RECALL_WEIGHTS

    def calculate_importance(
        self,
        event: MemoryEvent,
        context: ScoringContext | None = None,
    ) -> float:
        """
        Calculate importance score for a memory event.

        Args:
            event: The memory event to score
            context: Additional context for scoring

        Returns:
            Importance score between 0.0 and 1.0
        """
        ctx = context or ScoringContext()
        w = self.importance_weights

        # Start with memory type base weight
        memory_type = event.memory_type.value
        base_weight = MEMORY_TYPE_BASE_WEIGHTS.get(memory_type, 0.5)

        # Calculate individual components
        outcome_score = self._calculate_outcome_score(event, ctx)
        reuse_score = self._calculate_reuse_score(event, ctx)
        cross_impact_score = self._calculate_cross_impact_score(event, ctx)
        novelty_score = self._calculate_novelty_score(event, ctx)
        user_signal_score = self._calculate_user_signal_score(event, ctx)
        cost_reduction_score = self._calculate_cost_reduction_score(event, ctx)

        # Combine base weight (40%) with dynamic factors (60%)
        score = 0.4 * base_weight + 0.6 * (
            w.outcome * outcome_score
            + w.reuse * reuse_score
            + w.cross_impact * cross_impact_score
            + w.novelty * novelty_score
            + w.user_signal * user_signal_score
            + w.cost_reduction * cost_reduction_score
        )

        return min(max(score, 0.0), 1.0)

    def calculate_recall(
        self,
        event: MemoryEvent,
        query_context: ScoringContext | None = None,
        stored_importance: float | None = None,
    ) -> float:
        """
        Calculate recall score for a memory event.

        Higher score = more relevant for retrieval.

        Args:
            event: The memory event to score
            query_context: Context of the current query/tool use
            stored_importance: Pre-calculated importance score (from storage)

        Returns:
            Recall score between 0.0 and 1.0
        """
        ctx = query_context or ScoringContext()
        w = self.recall_weights

        # Get importance score
        importance_score = stored_importance
        if importance_score is None:
            importance_score = event.metadata.get("importance_score", 0.5)

        # Calculate recency
        recency_score = self._calculate_recency_score(event)

        # Calculate role fit
        role_fit_score = self._calculate_role_fit_score(event, ctx)

        # Calculate outcome relevance
        outcome_score = self._calculate_outcome_relevance_score(event, ctx)

        # Weighted sum
        base_score = (
            w.importance * importance_score
            + w.recency * recency_score
            + w.role_fit * role_fit_score
            + w.outcome * outcome_score
        )

        # Apply rule-based boosts
        boosted_score = self._apply_recall_boosts(event, ctx, base_score)

        return min(max(boosted_score, 0.0), 1.0)

    # =========================================================================
    # Importance Score Components
    # =========================================================================

    def _calculate_outcome_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on outcome (success/failure).

        Failures are MORE important for learning (avoid repeating mistakes).
        """
        # Check metadata for outcome
        outcome = event.metadata.get("outcome", "unknown")

        # Failures are MORE important for learning
        if outcome == "failure":
            return 1.0
        elif outcome == "success":
            return 0.8
        elif outcome == "partial":
            return 0.7
        else:
            # Default based on context
            if ctx.tool_success:
                return 0.6
            return 0.5

    def _calculate_reuse_score(self, event: MemoryEvent, ctx: ScoringContext) -> float:
        """Score based on potential for reuse."""
        # Check if this is a pattern that could be reused
        reuse_count = ctx.past_reuse_count
        memory_type = event.memory_type.value

        # Some types are more reusable
        type_multiplier = {
            "preference": 1.0,  # Always applicable
            "workflow": 0.9,  # Often applicable
            "error": 0.8,  # Valuable for avoiding mistakes
            "decision": 0.7,  # Context-dependent
            "observation": 0.5,  # Usually one-time
            "plan": 0.4,  # Usually specific
            "artifact": 0.3,  # Very specific
            "research": 0.6,  # Somewhat reusable
        }.get(memory_type, 0.5)

        # Boost based on past reuse
        if reuse_count > 0:
            reuse_boost = min(reuse_count / 10.0, 0.3)
            return min(type_multiplier + reuse_boost, 1.0)

        return type_multiplier

    def _calculate_cross_impact_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on cross-agent/cross-session impact."""
        scope = event.scope.value

        # Public memories have higher cross-impact
        scope_score = {
            "public": 1.0,
            "user": 0.7,
            "agent": 0.4,
            "session": 0.2,
        }.get(scope, 0.5)

        # Check for cross-session relevance in tags
        if event.tags:
            cross_tags = ["shared", "global", "important", "core"]
            if any(tag in cross_tags for tag in event.tags):
                scope_score = min(scope_score + 0.2, 1.0)

        return scope_score

    def _calculate_novelty_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on novelty (how unique is this memory)."""
        if ctx.similar_memory_count == 0:
            return 1.0  # Completely novel

        if ctx.total_memory_count == 0:
            return 0.8  # First memory

        # Inverse proportion to similar memories
        similarity_ratio = ctx.similar_memory_count / max(ctx.total_memory_count, 1)
        novelty = 1.0 - similarity_ratio

        return max(novelty, 0.1)  # Minimum 0.1

    def _calculate_user_signal_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on user signal (explicit feedback)."""
        # Normalize from -1..1 to 0..1
        signal = ctx.user_signal
        normalized = (signal + 1.0) / 2.0

        # Check for explicit user tags
        if event.tags:
            if "important" in event.tags or "remember" in event.tags:
                normalized = max(normalized, 0.9)
            elif "ignore" in event.tags or "forget" in event.tags:
                normalized = min(normalized, 0.1)

        return normalized

    def _calculate_cost_reduction_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on potential cost reduction."""
        # Check if this memory helps avoid expensive operations
        memory_type = event.memory_type.value

        # Error patterns help avoid retries
        if memory_type == "error":
            return 0.9

        # Cached results reduce API calls
        if memory_type == "research" or memory_type == "artifact":
            return 0.7

        # Decisions help avoid re-analysis
        if memory_type == "decision":
            return 0.6

        return 0.4  # Default

    # =========================================================================
    # Recall Score Components
    # =========================================================================

    def _calculate_recency_score(self, event: MemoryEvent) -> float:
        """Score based on how recent the memory is."""
        try:
            created_at = datetime.fromisoformat(event.created_at)
            now = datetime.now()
            age_days = (now - created_at).days

            # Exponential decay
            # 0 days = 1.0, 7 days ≈ 0.5, 30 days ≈ 0.1
            if age_days <= 0:
                return 1.0
            elif age_days <= 7:  # Hot tier
                return 1.0 - (age_days / 7.0) * 0.5
            elif age_days <= 30:  # Warm tier
                return 0.5 - ((age_days - 7) / 23.0) * 0.4
            else:  # Cold tier
                return max(0.1 - ((age_days - 30) / 365.0) * 0.09, 0.01)
        except (ValueError, TypeError):
            return 0.5  # Default for invalid dates

    def _calculate_role_fit_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on how well memory fits current agent role."""
        if not ctx.agent_role:
            return 0.5  # No role specified

        event_agent = event.source_agent.value
        current_role = ctx.agent_role.lower()

        # Direct match
        if event_agent == current_role:
            return 1.0

        # Cross-agent relevance matrix
        relevance = {
            ("codex", "claude"): 0.8,  # Codex findings useful for Claude
            ("gemini", "claude"): 0.7,  # Research useful for Claude
            ("claude", "codex"): 0.6,  # Claude context for Codex
            ("gemini", "codex"): 0.7,  # Research for Codex
        }

        return relevance.get((event_agent, current_role), 0.4)

    def _calculate_outcome_relevance_score(
        self, event: MemoryEvent, ctx: ScoringContext
    ) -> float:
        """Score based on outcome relevance to current context."""
        outcome = event.metadata.get("outcome", "unknown")

        # Failures are highly relevant (avoid repeating)
        if outcome == "failure" and ctx.tool_name:
            # Check if same tool type
            event_tool = event.metadata.get("tool_name", "")
            if event_tool and event_tool == ctx.tool_name:
                return 1.0  # Very relevant - same tool failed before
            return 0.8  # Relevant - a failure pattern

        # Successes are useful templates
        if outcome == "success":
            return 0.6

        return 0.5  # Neutral

    def _apply_recall_boosts(
        self, event: MemoryEvent, ctx: ScoringContext, base_score: float
    ) -> float:
        """Apply rule-based boosts to recall score."""
        score = base_score

        # Boost 1: Same task_id
        if ctx.task_id and event.metadata.get("task_id") == ctx.task_id:
            score += 0.15

        # Boost 2: Same session
        if ctx.session_id and event.metadata.get("session_id") == ctx.session_id:
            score += 0.1

        # Boost 3: Failure patterns for same tool
        if ctx.tool_name:
            event_tool = event.metadata.get("tool_name", "")
            outcome = event.metadata.get("outcome", "")
            if event_tool == ctx.tool_name and outcome == "failure":
                score += 0.2  # Prioritize failure warnings

        # Boost 4: High confidence
        if event.confidence >= 0.9:
            score += 0.05

        return score


# Memory type base weights for importance scoring
# These represent inherent importance of each memory type
MEMORY_TYPE_BASE_WEIGHTS = {
    "preference": 0.9,  # High - Directly impacts behavior
    "workflow": 0.8,  # High - Repeated patterns
    "decision": 0.85,  # High - Architecture choices
    "error": 0.7,  # Medium - Context-dependent learning
    "observation": 0.5,  # Low - Routine actions
    "research": 0.75,  # Medium-High - Investigation results
    "plan": 0.8,  # High - Strategic planning
    "artifact": 0.7,  # Medium - Concrete outputs
}


# Global engine instance
_engine: ScoringEngine | None = None


def get_scoring_engine(
    importance_weights: ImportanceWeights | None = None,
    recall_weights: RecallWeights | None = None,
) -> ScoringEngine:
    """Get or create global scoring engine instance."""
    global _engine
    if _engine is None:
        _engine = ScoringEngine(importance_weights, recall_weights)
    return _engine


def calculate_importance_score(
    event: MemoryEvent,
    context: ScoringContext | None = None,
) -> float:
    """Convenience function to calculate importance score."""
    return get_scoring_engine().calculate_importance(event, context)


def calculate_recall_score(
    event: MemoryEvent,
    query_context: ScoringContext | None = None,
    stored_importance: float | None = None,
) -> float:
    """Convenience function to calculate recall score."""
    return get_scoring_engine().calculate_recall(
        event, query_context, stored_importance
    )

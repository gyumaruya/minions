"""
Policy Manager - Self-improvement parameter management.

Manages recall parameters and scoring weights based on
observed performance and contribution metrics.

Based on the self-improvement memory cycle design.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RecallPolicy:
    """Policy for memory recall."""

    top_k: int = 5  # Maximum memories to recall
    min_score: float = 0.5  # Minimum recall score threshold
    enable_semantic: bool = True  # Use semantic search (mem0)
    boost_same_task: float = 0.15  # Score boost for same task_id
    boost_same_session: float = 0.1  # Score boost for same session
    boost_failure_pattern: float = 0.2  # Score boost for failure warnings


@dataclass
class ScoringPolicy:
    """Policy for importance and recall scoring."""

    # Importance weights (sum to 1.0)
    importance_outcome: float = 0.25
    importance_reuse: float = 0.20
    importance_cross_impact: float = 0.20
    importance_novelty: float = 0.15
    importance_user_signal: float = 0.15
    importance_cost_reduction: float = 0.05

    # Recall weights (sum to 1.0)
    recall_importance: float = 0.4
    recall_recency: float = 0.3
    recall_role_fit: float = 0.2
    recall_outcome: float = 0.1


@dataclass
class ExclusionRule:
    """Rule to exclude low-contribution patterns."""

    pattern: str  # Pattern to match (e.g., "tool:Read", "type:observation")
    reason: str  # Why excluded
    created_at: str  # When rule was created


class PolicyManager:
    """Manager for self-improvement policies."""

    def __init__(self, policy_dir: Path | None = None):
        """Initialize policy manager."""
        self.policy_dir = policy_dir or Path.home() / "minions" / ".claude" / "memory"
        self.policy_dir.mkdir(parents=True, exist_ok=True)

        self.recall_policy_file = self.policy_dir / "recall_policy.json"
        self.scoring_policy_file = self.policy_dir / "scoring_policy.json"
        self.exclusion_rules_file = self.policy_dir / "exclusion_rules.jsonl"

        # Load or create default policies
        self.recall_policy = self._load_recall_policy()
        self.scoring_policy = self._load_scoring_policy()
        self.exclusion_rules = self._load_exclusion_rules()

    # =========================================================================
    # Policy Loading
    # =========================================================================

    def _load_recall_policy(self) -> RecallPolicy:
        """Load recall policy from file or create default."""
        if self.recall_policy_file.exists():
            try:
                with open(self.recall_policy_file, encoding="utf-8") as f:
                    data = json.load(f)
                return RecallPolicy(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return RecallPolicy()

    def _load_scoring_policy(self) -> ScoringPolicy:
        """Load scoring policy from file or create default."""
        if self.scoring_policy_file.exists():
            try:
                with open(self.scoring_policy_file, encoding="utf-8") as f:
                    data = json.load(f)
                return ScoringPolicy(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return ScoringPolicy()

    def _load_exclusion_rules(self) -> list[ExclusionRule]:
        """Load exclusion rules from file."""
        if not self.exclusion_rules_file.exists():
            return []

        rules = []
        with open(self.exclusion_rules_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        rules.append(ExclusionRule(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        return rules

    # =========================================================================
    # Policy Saving
    # =========================================================================

    def save_recall_policy(self) -> None:
        """Save recall policy to file."""
        with open(self.recall_policy_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.recall_policy), f, ensure_ascii=False, indent=2)

    def save_scoring_policy(self) -> None:
        """Save scoring policy to file."""
        with open(self.scoring_policy_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.scoring_policy), f, ensure_ascii=False, indent=2)

    def save_exclusion_rules(self) -> None:
        """Save exclusion rules to file."""
        with open(self.exclusion_rules_file, "w", encoding="utf-8") as f:
            for rule in self.exclusion_rules:
                f.write(json.dumps(asdict(rule), ensure_ascii=False) + "\n")

    # =========================================================================
    # Policy Updates
    # =========================================================================

    def update_recall_threshold(self, min_score: float) -> None:
        """Update minimum recall score threshold."""
        self.recall_policy.min_score = max(0.0, min(min_score, 1.0))
        self.save_recall_policy()

    def update_recall_top_k(self, top_k: int) -> None:
        """Update number of memories to recall."""
        self.recall_policy.top_k = max(1, min(top_k, 20))
        self.save_recall_policy()

    def adjust_importance_weights(
        self,
        outcome: float | None = None,
        reuse: float | None = None,
        cross_impact: float | None = None,
        novelty: float | None = None,
        user_signal: float | None = None,
        cost_reduction: float | None = None,
    ) -> None:
        """
        Adjust importance scoring weights.

        Weights are normalized to sum to 1.0.
        """
        weights = [
            outcome or self.scoring_policy.importance_outcome,
            reuse or self.scoring_policy.importance_reuse,
            cross_impact or self.scoring_policy.importance_cross_impact,
            novelty or self.scoring_policy.importance_novelty,
            user_signal or self.scoring_policy.importance_user_signal,
            cost_reduction or self.scoring_policy.importance_cost_reduction,
        ]

        # Normalize
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        (
            self.scoring_policy.importance_outcome,
            self.scoring_policy.importance_reuse,
            self.scoring_policy.importance_cross_impact,
            self.scoring_policy.importance_novelty,
            self.scoring_policy.importance_user_signal,
            self.scoring_policy.importance_cost_reduction,
        ) = weights

        self.save_scoring_policy()

    def adjust_recall_weights(
        self,
        importance: float | None = None,
        recency: float | None = None,
        role_fit: float | None = None,
        outcome: float | None = None,
    ) -> None:
        """
        Adjust recall scoring weights.

        Weights are normalized to sum to 1.0.
        """
        weights = [
            importance or self.scoring_policy.recall_importance,
            recency or self.scoring_policy.recall_recency,
            role_fit or self.scoring_policy.recall_role_fit,
            outcome or self.scoring_policy.recall_outcome,
        ]

        # Normalize
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        (
            self.scoring_policy.recall_importance,
            self.scoring_policy.recall_recency,
            self.scoring_policy.recall_role_fit,
            self.scoring_policy.recall_outcome,
        ) = weights

        self.save_scoring_policy()

    # =========================================================================
    # Exclusion Rules
    # =========================================================================

    def add_exclusion_rule(self, pattern: str, reason: str) -> None:
        """Add a pattern exclusion rule."""
        from datetime import datetime

        rule = ExclusionRule(
            pattern=pattern, reason=reason, created_at=datetime.now().isoformat()
        )
        self.exclusion_rules.append(rule)
        self.save_exclusion_rules()

    def remove_exclusion_rule(self, pattern: str) -> bool:
        """Remove an exclusion rule by pattern."""
        before_count = len(self.exclusion_rules)
        self.exclusion_rules = [r for r in self.exclusion_rules if r.pattern != pattern]
        removed = len(self.exclusion_rules) < before_count
        if removed:
            self.save_exclusion_rules()
        return removed

    def is_excluded(self, pattern: str) -> bool:
        """Check if a pattern is excluded."""
        return any(rule.pattern == pattern for rule in self.exclusion_rules)

    # =========================================================================
    # Contribution-based Updates
    # =========================================================================

    def evaluate_contribution(
        self, pattern: str, contribution_score: float, sample_size: int = 10
    ) -> None:
        """
        Evaluate pattern contribution and update policy if needed.

        Args:
            pattern: Pattern to evaluate (e.g., "tool:Bash", "type:observation")
            contribution_score: Score from 0 (no contribution) to 1 (high contribution)
            sample_size: Number of samples used for evaluation
        """
        # If consistently low contribution over sufficient samples, exclude
        if sample_size >= 10 and contribution_score < 0.2:
            if not self.is_excluded(pattern):
                self.add_exclusion_rule(
                    pattern, f"Low contribution ({contribution_score:.2f})"
                )

        # If excluded pattern shows high contribution, remove exclusion
        elif contribution_score >= 0.7 and self.is_excluded(pattern):
            self.remove_exclusion_rule(pattern)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_current_policies(self) -> dict:
        """Get current policies as dict."""
        return {
            "recall": asdict(self.recall_policy),
            "scoring": asdict(self.scoring_policy),
            "exclusions": [asdict(rule) for rule in self.exclusion_rules],
        }


# Global policy manager instance
_policy_manager: PolicyManager | None = None


def get_policy_manager() -> PolicyManager:
    """Get or create global policy manager instance."""
    global _policy_manager
    if _policy_manager is None:
        _policy_manager = PolicyManager()
    return _policy_manager

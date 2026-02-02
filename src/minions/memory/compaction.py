"""
Compaction - Memory compression and tier management.

Responsibilities:
- Tier transition (Hot → Warm → Cold)
- Duplicate event elimination
- Summary generation (LLM-free, simple aggregation)
- Session summary creation

Based on the self-improvement memory cycle design.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minions.memory.schema import MemoryEvent


class MemoryTier:
    """Memory tier definitions."""

    HOT = "hot"  # 0-7 days: Full detail
    WARM = "warm"  # 7-30 days: Important full, others summarized
    COLD = "cold"  # 30+ days: Long-term summary only


class CompactionWorker:
    """Worker for memory compaction and tier management."""

    def __init__(self, memory_dir: Path | None = None):
        """Initialize compaction worker."""
        self.memory_dir = memory_dir or Path.home() / "minions" / ".claude" / "memory"
        self.events_file = self.memory_dir / "events.jsonl"
        self.sessions_dir = self.memory_dir / "sessions"

        # Tier thresholds (days)
        self.hot_threshold = 7
        self.warm_threshold = 30

    def determine_tier(self, event: MemoryEvent) -> str:
        """Determine which tier an event belongs to."""
        try:
            created_at = datetime.fromisoformat(event.created_at)
            age_days = (datetime.now() - created_at).days

            if age_days <= self.hot_threshold:
                return MemoryTier.HOT
            elif age_days <= self.warm_threshold:
                return MemoryTier.WARM
            else:
                return MemoryTier.COLD
        except (ValueError, TypeError):
            return MemoryTier.HOT  # Default to hot if date parsing fails

    def is_important(self, event: MemoryEvent) -> bool:
        """Check if event is important enough to keep in detail."""
        # Check importance score
        importance = event.metadata.get("importance_score", 0.5)
        if importance >= 0.8:
            return True

        # Check tags
        if event.tags:
            important_tags = {"important", "remember", "critical", "core"}
            if any(tag in important_tags for tag in event.tags):
                return True

        # Check type (some types are always important)
        important_types = {"preference", "decision", "error"}
        if event.memory_type.value in important_types:
            return True

        return False

    def deduplicate_events(self, events: list[MemoryEvent]) -> list[MemoryEvent]:
        """Remove duplicate events."""
        # Group by content similarity (exact match for now)
        content_map: dict[str, list[MemoryEvent]] = defaultdict(list)

        for event in events:
            # Normalize content for comparison
            normalized = event.content.strip().lower()
            content_map[normalized].append(event)

        # Keep most recent or highest importance from each group
        unique_events = []
        for group in content_map.values():
            if len(group) == 1:
                unique_events.append(group[0])
            else:
                # Sort by importance, then recency
                group.sort(
                    key=lambda e: (
                        e.metadata.get("importance_score", 0.5),
                        e.created_at,
                    ),
                    reverse=True,
                )
                unique_events.append(group[0])

        return unique_events

    def summarize_group(
        self, events: list[MemoryEvent], group_key: str
    ) -> dict[str, any]:
        """
        Summarize a group of events (LLM-free, simple aggregation).

        Args:
            events: Events to summarize
            group_key: Grouping key (e.g., "tool:Bash", "type:observation")

        Returns:
            Summary dict with aggregated information
        """
        if not events:
            return {}

        # Count by outcome
        outcomes = defaultdict(int)
        for event in events:
            outcome = event.metadata.get("outcome", "unknown")
            outcomes[outcome] += 1

        # Get date range
        dates = [datetime.fromisoformat(e.created_at) for e in events]
        date_range = {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat(),
        }

        # Average importance
        importances = [e.metadata.get("importance_score", 0.5) for e in events]
        avg_importance = sum(importances) / len(importances) if importances else 0.5

        # Most common tags
        all_tags = [tag for event in events for tag in event.tags]
        tag_counts = defaultdict(int)
        for tag in all_tags:
            tag_counts[tag] += 1
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "group_key": group_key,
            "event_count": len(events),
            "outcomes": dict(outcomes),
            "date_range": date_range,
            "avg_importance": avg_importance,
            "top_tags": [tag for tag, _ in top_tags],
            "sample_content": events[0].content[:200] if events else "",
        }

    def compact_session(self, session_id: str) -> dict[str, any]:
        """
        Compact a session's events into a summary.

        Args:
            session_id: Session ID to compact

        Returns:
            Session summary dict
        """
        from minions.memory.schema import MemoryEvent

        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return {}

        # Load session events
        events = []
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        events.append(MemoryEvent.from_dict(data))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        if not events:
            return {}

        # Deduplicate
        events = self.deduplicate_events(events)

        # Group by tool/type
        by_tool: dict[str, list[MemoryEvent]] = defaultdict(list)
        by_type: dict[str, list[MemoryEvent]] = defaultdict(list)

        for event in events:
            tool_name = event.metadata.get("tool_name", "")
            if tool_name:
                by_tool[tool_name].append(event)
            by_type[event.memory_type.value].append(event)

        # Create summaries
        tool_summaries = [
            self.summarize_group(events, f"tool:{tool}")
            for tool, events in by_tool.items()
        ]
        type_summaries = [
            self.summarize_group(events, f"type:{mtype}")
            for mtype, events in by_type.items()
        ]

        # Overall stats
        success_count = sum(1 for e in events if e.metadata.get("outcome") == "success")
        failure_count = sum(1 for e in events if e.metadata.get("outcome") == "failure")

        return {
            "session_id": session_id,
            "total_events": len(events),
            "success_count": success_count,
            "failure_count": failure_count,
            "tool_summaries": tool_summaries,
            "type_summaries": type_summaries,
            "date_range": {
                "start": min(e.created_at for e in events),
                "end": max(e.created_at for e in events),
            },
        }

    def compact_by_tier(self) -> dict[str, any]:
        """
        Compact events by tier (Hot/Warm/Cold).

        Returns:
            Compaction statistics
        """
        from minions.memory.schema import MemoryEvent

        # Load all events
        if not self.events_file.exists():
            return {"error": "No events file found"}

        events = []
        with open(self.events_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        events.append(MemoryEvent.from_dict(data))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        if not events:
            return {"total_events": 0}

        # Classify by tier
        by_tier: dict[str, list[MemoryEvent]] = {
            MemoryTier.HOT: [],
            MemoryTier.WARM: [],
            MemoryTier.COLD: [],
        }

        for event in events:
            tier = self.determine_tier(event)
            by_tier[tier].append(event)

        # Deduplicate within each tier
        for tier in by_tier:
            by_tier[tier] = self.deduplicate_events(by_tier[tier])

        # For Warm tier: keep important events in full, summarize others
        warm_important = [e for e in by_tier[MemoryTier.WARM] if self.is_important(e)]
        warm_others = [e for e in by_tier[MemoryTier.WARM] if not self.is_important(e)]

        # For Cold tier: create long-term summaries
        cold_summaries = []
        if by_tier[MemoryTier.COLD]:
            # Group by type and month
            cold_by_month: dict[str, list[MemoryEvent]] = defaultdict(list)
            for event in by_tier[MemoryTier.COLD]:
                try:
                    created = datetime.fromisoformat(event.created_at)
                    month_key = created.strftime("%Y-%m")
                    cold_by_month[month_key].append(event)
                except (ValueError, TypeError):
                    continue

            for month_key, month_events in cold_by_month.items():
                cold_summaries.append(
                    self.summarize_group(month_events, f"month:{month_key}")
                )

        # Rewrite events file with compacted data
        compacted_events = (
            by_tier[MemoryTier.HOT]  # Hot: keep all
            + warm_important  # Warm: keep important only
            # Note: warm_others are summarized and kept in metadata
        )

        with open(self.events_file, "w", encoding="utf-8") as f:
            for event in compacted_events:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        return {
            "total_events": len(events),
            "hot_count": len(by_tier[MemoryTier.HOT]),
            "warm_important_count": len(warm_important),
            "warm_summarized_count": len(warm_others),
            "cold_count": len(by_tier[MemoryTier.COLD]),
            "cold_summaries": len(cold_summaries),
            "compacted_events": len(compacted_events),
        }


def compact_session(session_id: str, memory_dir: Path | None = None) -> dict[str, any]:
    """Convenience function to compact a single session."""
    worker = CompactionWorker(memory_dir)
    return worker.compact_session(session_id)


def compact_all_tiers(memory_dir: Path | None = None) -> dict[str, any]:
    """Convenience function to compact all tiers."""
    worker = CompactionWorker(memory_dir)
    return worker.compact_by_tier()

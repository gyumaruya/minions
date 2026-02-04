#!/usr/bin/env python3
"""
Hook: Session end processing.

Performs end-of-session tasks:
- Session summary generation
- Memory compaction (tier transition)
- Self-improvement evaluation

Phase: ORGANIZE + IMPROVE
Trigger: SessionEnd (manual, not auto-registered yet)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def generate_session_summary(session_id: str) -> dict:
    """Generate summary for the current session."""
    try:
        from minions.memory.compaction import compact_session

        summary = compact_session(session_id)
        return summary

    except Exception as e:
        print(f"[session-end] Summary generation failed: {e}", file=sys.stderr)
        return {}


def run_compaction() -> dict:
    """Run memory compaction (tier transition)."""
    try:
        from minions.memory.compaction import compact_all_tiers

        stats = compact_all_tiers()
        return stats

    except Exception as e:
        print(f"[session-end] Compaction failed: {e}", file=sys.stderr)
        return {}


def evaluate_self_improvement(session_id: str, summary: dict) -> dict:
    """
    Evaluate self-improvement based on session results.

    Returns:
        Evaluation metrics and policy updates
    """
    # TODO: Implement policy updates based on session performance
    # For now, just compute basic metrics

    total = summary.get("total_events", 0)
    success = summary.get("success_count", 0)
    failure = summary.get("failure_count", 0)

    if total == 0:
        return {"session_id": session_id, "metrics": {}}

    success_rate = success / total if total > 0 else 0.0
    failure_rate = failure / total if total > 0 else 0.0

    metrics = {
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "total_events": total,
    }

    # Determine if this was a good session
    performance = "good" if success_rate >= 0.7 else "needs_improvement"

    return {
        "session_id": session_id,
        "metrics": metrics,
        "performance": performance,
    }


def save_session_report(session_id: str, summary: dict, evaluation: dict) -> None:
    """Save session report for future reference."""
    try:
        report_dir = Path.home() / "minions" / ".claude" / "memory" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / f"{session_id}.json"

        report = {
            "session_id": session_id,
            "summary": summary,
            "evaluation": evaluation,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"[session-end] Report saved: {report_file}", file=sys.stderr)

    except Exception as e:
        print(f"[session-end] Report save failed: {e}", file=sys.stderr)


def main() -> None:
    """Main hook entry point."""
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        pass

    # Get session ID
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Generate session summary
    print("[session-end] Generating session summary...", file=sys.stderr)
    summary = generate_session_summary(session_id)

    # Run compaction (tier transition)
    print("[session-end] Running memory compaction...", file=sys.stderr)
    compaction_stats = run_compaction()

    # Evaluate self-improvement
    print("[session-end] Evaluating session performance...", file=sys.stderr)
    evaluation = evaluate_self_improvement(session_id, summary)

    # Save report
    save_session_report(session_id, summary, evaluation)

    # Output summary to user
    output_lines = [
        "\n# セッション終了レポート\n",
        f"セッションID: {session_id}",
        f"処理イベント数: {summary.get('total_events', 0)}",
        f"成功: {summary.get('success_count', 0)} / 失敗: {summary.get('failure_count', 0)}",
        f"\nメモリ圧縮: {compaction_stats.get('compacted_events', 0)} イベントを保持",
        f"パフォーマンス: {evaluation.get('performance', 'unknown')}",
    ]

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionEnd",
                "additionalContext": "\n".join(output_lines),
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()

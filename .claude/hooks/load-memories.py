#!/usr/bin/env python3
"""
Hook: Load relevant memories at session start.

Injects relevant memories (preferences, workflows, recent errors)
into the conversation context to guide behavior.

This hook runs on first UserPromptSubmit of a session.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import config utilities
from config_utils import get_openai_api_key

# State file to track if we've loaded memories this session
# Use parent PID (Claude Code process) to identify session
_ppid = os.environ.get("CLAUDE_SESSION_ID", str(os.getppid()))
STATE_FILE = Path("/tmp") / f"claude-memory-loaded-{_ppid}.flag"


def get_relevant_memories() -> list[dict]:
    """Get relevant memories directly."""
    try:
        from minions.memory import MemoryBroker, MemoryScope, MemoryType

        # Try to get API key (cross-platform)
        api_key = get_openai_api_key()
        enable_mem0 = False

        if api_key:
            # Set environment variable for mem0
            os.environ["OPENAI_API_KEY"] = api_key
            enable_mem0 = True

            # Log to stderr for hook debugging
            print("[load-memories] mem0 enabled via API key", file=sys.stderr)
        else:
            print(
                "[load-memories] API key not found, using JSONL fallback",
                file=sys.stderr,
            )

        broker = MemoryBroker(enable_mem0=enable_mem0)
        memories = []

        # Get user preferences
        prefs = broker.search(
            query="",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            limit=5,
            use_semantic=False,
        )
        memories.extend([e.to_dict() for e in prefs])

        # Get workflows
        workflows = broker.search(
            query="",
            memory_type=MemoryType.WORKFLOW,
            scope=MemoryScope.USER,
            limit=3,
            use_semantic=False,
        )
        memories.extend([e.to_dict() for e in workflows])

        # Get recent errors
        errors = broker.search(
            query="",
            memory_type=MemoryType.ERROR,
            limit=3,
            use_semantic=False,
        )
        memories.extend([e.to_dict() for e in errors])

        # Dedupe by content
        seen = set()
        unique = []
        for m in memories:
            if m["content"] not in seen:
                seen.add(m["content"])
                unique.append(m)

        return unique

    except Exception:
        return []


def format_memories_for_context(memories: list[dict]) -> str:
    """Format memories as context for Claude."""
    if not memories:
        return ""

    lines = ["# 記憶から読み込んだ情報\n"]

    # Group by type
    by_type: dict[str, list[str]] = {}
    for m in memories:
        mtype = m.get("memory_type", "other")
        content = m.get("content", "")
        if mtype not in by_type:
            by_type[mtype] = []
        by_type[mtype].append(content)

    type_labels = {
        "preference": "ユーザーの好み",
        "workflow": "ワークフロー",
        "error": "過去のエラーパターン",
        "decision": "設計判断",
    }

    for mtype, contents in by_type.items():
        label = type_labels.get(mtype, mtype)
        lines.append(f"\n## {label}\n")
        for content in contents:
            lines.append(f"- {content}")

    lines.append("\n---\n")
    return "\n".join(lines)


def main() -> None:
    """Main hook entry point."""
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Check if we've already loaded memories this session
    if STATE_FILE.exists():
        sys.exit(0)

    # Mark as loaded
    STATE_FILE.touch()

    # Get relevant memories
    memories = get_relevant_memories()

    if not memories:
        sys.exit(0)

    # Format and inject as context
    context = format_memories_for_context(memories)

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

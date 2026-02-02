#!/usr/bin/env python3
"""
Hook: Recall relevant memories before tool execution.

Searches for related memories before executing tools and injects
them as additional context for better decision-making.

Phase: RECALL
Trigger: PreToolUse
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Tools that benefit from memory recall
RECALL_TOOLS = {
    "Bash": True,
    "Edit": True,
    "Write": True,
    "Task": True,
    "WebFetch": True,
    "WebSearch": True,
}

# Maximum memories to inject
MAX_RECALL = 5

# Tool-specific score thresholds
TOOL_SCORE_THRESHOLDS = {
    "Bash": 0.6,  # Command execution — prioritize failure patterns
    "Edit": 0.7,  # File editing — high relevance only
    "Write": 0.7,  # File creation — high relevance only
    "Task": 0.5,  # Subagent — broader reference
    "WebFetch": 0.8,  # Web fetch — very high relevance only
    "WebSearch": 0.8,  # Web search — very high relevance only
}


def get_score_threshold(tool_name: str) -> float:
    """Get score threshold for tool type."""
    return TOOL_SCORE_THRESHOLDS.get(tool_name, 0.7)  # Default 0.7


def get_openai_api_key_from_keychain() -> str | None:
    """Get OpenAI API key from macOS Keychain."""
    try:
        username = os.environ.get("USER", "")
        if not username:
            return None

        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                username,
                "-s",
                "openai-api-key",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            api_key = result.stdout.strip()
            return api_key if api_key else None

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return None


def build_search_query(tool_name: str, tool_input: dict) -> str:
    """Build search query from tool context."""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Extract first meaningful line
        first_line = command.split("\n")[0][:100]
        # Extract command name
        cmd_name = first_line.split()[0] if first_line else ""
        return f"command {cmd_name}"

    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        return f"edit {Path(file_path).name}"

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        return f"create {Path(file_path).name}"

    elif tool_name == "Task":
        prompt = tool_input.get("prompt", "")[:200]
        return prompt

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        return f"fetch {url}"

    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return query

    return tool_name


def recall_memories(tool_name: str, tool_input: dict) -> list[dict]:
    """Recall relevant memories for tool execution."""
    try:
        from minions.memory import MemoryBroker
        from minions.memory.scoring import ScoringContext, calculate_recall_score

        # Try to get API key from Keychain
        api_key = get_openai_api_key_from_keychain()
        enable_mem0 = False

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            enable_mem0 = True

        broker = MemoryBroker(enable_mem0=enable_mem0)

        # Build search query
        query = build_search_query(tool_name, tool_input)

        # Get session and task context
        session_id = os.environ.get("CLAUDE_SESSION_ID")
        task_id = None  # TODO: Extract from tool_input if available

        # Create scoring context for recall
        scoring_ctx = ScoringContext(
            tool_name=tool_name,
            session_id=session_id,
            task_id=task_id,
        )

        # Search memories
        memories = broker.search(
            query=query,
            limit=MAX_RECALL * 2,  # Get more, then filter by score
            use_semantic=enable_mem0,
        )

        # Score and filter with tool-specific threshold
        threshold = get_score_threshold(tool_name)
        scored_memories = []
        for event in memories:
            stored_importance = event.metadata.get("importance_score")
            recall_score = calculate_recall_score(event, scoring_ctx, stored_importance)

            # Only include memories above tool-specific threshold
            if recall_score >= threshold:
                scored_memories.append(
                    {
                        "event": event,
                        "score": recall_score,
                    }
                )

        # Sort by score and take top-k
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        top_memories = scored_memories[:MAX_RECALL]

        # Convert to dict format
        return [
            {
                "content": m["event"].content,
                "type": m["event"].memory_type.value,
                "score": m["score"],
                "created_at": m["event"].created_at,
            }
            for m in top_memories
        ]

    except Exception as e:
        print(f"[pre-tool-recall] Error: {e}", file=sys.stderr)
        return []


def format_memories_for_context(memories: list[dict]) -> str:
    """Format memories as context for tool execution."""
    if not memories:
        return ""

    lines = ["# 関連する記憶\n"]

    for i, m in enumerate(memories, 1):
        content = m["content"]
        mtype = m["type"]
        score = m["score"]

        # Truncate long content
        if len(content) > 150:
            content = content[:147] + "..."

        lines.append(f"{i}. [{mtype}] {content} (関連度: {score:.2f})")

    lines.append("\n---\n")
    return "\n".join(lines)


def main() -> None:
    """Main hook entry point."""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Get tool information
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Skip tools that don't benefit from recall
    if tool_name not in RECALL_TOOLS:
        sys.exit(0)

    # Recall relevant memories
    memories = recall_memories(tool_name, tool_input)

    if not memories:
        sys.exit(0)

    # Format and inject as context
    context = format_memories_for_context(memories)

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

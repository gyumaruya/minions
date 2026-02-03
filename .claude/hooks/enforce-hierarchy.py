#!/usr/bin/env python3
"""
PreToolUse hook: Enforce agent hierarchy.

Prevents upper-level agents (Conductor, Section Leader) from doing
direct implementation work. They must delegate to lower-level agents.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def get_agent_role() -> str:
    """Determine the current agent's role."""
    role = os.environ.get("AGENT_ROLE", "").lower()
    if role in ("conductor", "section_leader", "musician"):
        return role

    # Default: subagents are Musicians (safe default)
    # Main session (Conductor) should explicitly set AGENT_ROLE=conductor
    return "musician"


def is_allowed_file(file_path: str) -> bool:
    """Check if the file is allowed to be edited by upper agents."""
    path = Path(file_path)

    # Allow .claude/ config and documentation
    if ".claude" in path.parts:
        return True

    # Allow memory files
    if "memory" in path.parts:
        return True

    # Allow pyproject.toml, settings files
    if path.name in ("pyproject.toml", "settings.json", ".gitignore"):
        return True

    return False


def main():
    # Read input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only check Edit and Write tools
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    # Get file path
    file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""

    # Check if this file is allowed for upper agents
    if is_allowed_file(file_path):
        sys.exit(0)

    # Determine agent role
    role = get_agent_role()

    # Musicians can edit anything
    if role == "musician":
        sys.exit(0)

    # Conductor and Section Leader should NOT directly edit implementation files
    if role in ("conductor", "section_leader"):
        role_name = (
            "Conductor（指揮者）"
            if role == "conductor"
            else "Section Leader（セクションリーダー）"
        )

        message = f"""⛔ 階層違反: {role_name} は直接ファイルを編集できません。

【正しい方法】
Task ツールでサブエージェント（Musician）を spawn して委譲してください。

→ 詳細: .claude/rules/agent-hierarchy.md"""

        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": message,
                }
            },
            sys.stdout,
        )
        sys.exit(0)

    # Unknown role, allow
    sys.exit(0)


if __name__ == "__main__":
    # rust移行中のみ移譲を全て許可
    pass
    # main()

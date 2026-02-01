#!/usr/bin/env python3
"""
PostToolUse hook: Hierarchy permission notification.

When a Task tool spawns a subagent, this hook provides context about
the permission inheritance from the agent hierarchy.
"""
from __future__ import annotations

import json
import os
import sys


# Permission inheritance rules
HIERARCHY_PERMISSIONS = {
    "conductor": {
        "section_leader": [
            "Read(*)", "Edit(*)", "Write(*)", "Glob(*)", "Grep(*)",
            "Bash(*)", "Task(*)", "WebFetch(*)", "WebSearch(*)"
        ],
        "musician": [
            "Read(*)", "Edit(*)", "Write(*)", "Glob(*)", "Grep(*)",
            "Bash(git:*)", "Bash(jj:*)", "Bash(npm:*)", "Bash(pytest:*)"
        ],
    },
    "section_leader": {
        "musician": [
            "Read(*)", "Edit(*)", "Write(*)", "Glob(*)", "Grep(*)",
            "Bash(git:*)", "Bash(jj:*)", "Bash(npm:*)", "Bash(pytest:*)",
            "Bash(python:*)", "Bash(uv:*)"
        ],
    },
    "musician": {},
}


def get_agent_role() -> str:
    """Determine the current agent's role."""
    role = os.environ.get("AGENT_ROLE", "").lower()
    if role in HIERARCHY_PERMISSIONS:
        return role
    return "conductor"


def detect_target_role(prompt: str) -> str:
    """Detect the target role from the prompt content."""
    prompt_lower = prompt.lower()
    if "section_leader" in prompt_lower or "セクションリーダー" in prompt_lower:
        return "section_leader"
    if "musician" in prompt_lower or "演奏者" in prompt_lower:
        return "musician"
    return "musician"


def main():
    # Read input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")

    # Only process Task tool
    if tool_name != "Task":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    prompt = tool_input.get("prompt", "") if isinstance(tool_input, dict) else ""

    # Determine roles
    parent_role = get_agent_role()
    target_role = detect_target_role(prompt)

    # Get permissions to grant
    role_permissions = HIERARCHY_PERMISSIONS.get(parent_role, {})
    permissions = role_permissions.get(target_role, [])

    if permissions:
        message = f"Hierarchy: {parent_role} → {target_role}. Permissions auto-granted: {len(permissions)} scopes."
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": message
            }
        }, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()

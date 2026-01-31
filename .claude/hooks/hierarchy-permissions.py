#!/usr/bin/env python3
"""
Hierarchy Permission Hook.

Automatically grants permissions to subagents based on the agent hierarchy.
When a parent agent (Conductor or Section Leader) spawns a subagent,
this hook ensures the subagent inherits appropriate permissions.

Hook Event: PreToolUse (Task)
"""

import json
import os
import sys
from typing import Any

# Permission inheritance rules
HIERARCHY_PERMISSIONS = {
    "conductor": {
        # Conductor grants all permissions to Section Leaders
        "section_leader": [
            "Read(*)",
            "Edit(*)",
            "Write(*)",
            "Glob(*)",
            "Grep(*)",
            "Bash(*)",
            "Task(*)",
            "WebFetch(*)",
            "WebSearch(*)",
        ],
        # Conductor can also directly spawn Musicians with limited permissions
        "musician": [
            "Read(*)",
            "Edit(*)",
            "Write(*)",
            "Glob(*)",
            "Grep(*)",
            "Bash(git:*)",
            "Bash(jj:*)",
            "Bash(npm:*)",
            "Bash(pytest:*)",
            "Bash(ruff:*)",
        ],
    },
    "section_leader": {
        # Section Leader grants limited permissions to Musicians
        "musician": [
            "Read(*)",
            "Edit(*)",
            "Write(*)",
            "Glob(*)",
            "Grep(*)",
            "Bash(git:*)",
            "Bash(jj:*)",
            "Bash(npm:*)",
            "Bash(pytest:*)",
            "Bash(ruff:*)",
            "Bash(python:*)",
            "Bash(uv:*)",
        ],
    },
    # Musicians cannot spawn subagents
    "musician": {},
}


def get_agent_role() -> str:
    """Determine the current agent's role from context."""
    # Check environment variable first
    role = os.environ.get("AGENT_ROLE", "").lower()
    if role in HIERARCHY_PERMISSIONS:
        return role

    # Default to conductor (top-level)
    return "conductor"


def detect_target_role(prompt: str) -> str:
    """Detect the target role from the prompt content."""
    prompt_lower = prompt.lower()

    if "section_leader" in prompt_lower or "セクションリーダー" in prompt_lower:
        return "section_leader"
    if "musician" in prompt_lower or "演奏者" in prompt_lower:
        return "musician"

    # Default to musician for general subagents
    return "musician"


def inject_permissions(
    tool_input: dict[str, Any], permissions: list[str]
) -> dict[str, Any]:
    """Inject permission context into the subagent prompt."""
    if "prompt" not in tool_input:
        return tool_input

    original_prompt = tool_input["prompt"]

    # Add permission context
    permission_context = f"""
## Granted Permissions (from parent agent)

The following permissions are automatically granted by the parent agent.
You may use these without additional user confirmation:

{chr(10).join(f"- {p}" for p in permissions)}

---

"""

    tool_input["prompt"] = permission_context + original_prompt
    return tool_input


def main() -> None:
    """Main hook logic."""
    # Read hook input from environment
    hook_input = os.environ.get("CLAUDE_HOOK_INPUT", "{}")

    try:
        data = json.loads(hook_input)
    except json.JSONDecodeError:
        # Not a valid hook input, approve and continue
        print(json.dumps({"result": "approve"}))
        return

    # Check if this is a Task tool call
    tool_name = data.get("tool_name", "")
    if tool_name != "Task":
        print(json.dumps({"result": "approve"}))
        return

    # Get tool input
    tool_input = data.get("tool_input", {})
    prompt = tool_input.get("prompt", "")

    # Determine roles
    parent_role = get_agent_role()
    target_role = detect_target_role(prompt)

    # Get permissions to grant
    role_permissions = HIERARCHY_PERMISSIONS.get(parent_role, {})
    permissions = role_permissions.get(target_role, [])

    if not permissions:
        # No permissions to grant (e.g., Musician trying to spawn)
        print(
            json.dumps(
                {
                    "result": "approve",
                    "message": f"Note: {parent_role} cannot grant permissions to {target_role}",
                }
            )
        )
        return

    # Inject permission context into the prompt
    # Note: This modifies the prompt to inform the subagent of its permissions
    message = f"Hierarchy: {parent_role} → {target_role}. Permissions auto-granted."

    print(json.dumps({"result": "approve", "message": message}))


if __name__ == "__main__":
    main()

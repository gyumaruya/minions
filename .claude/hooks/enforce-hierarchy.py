#!/usr/bin/env python3
"""
Enforce Hierarchy Hook.

Prevents upper-level agents (Conductor, Section Leader) from doing
direct implementation work. They must delegate to lower-level agents.

Hook Event: PreToolUse (Edit, Write)

Violations:
- Conductor using Edit/Write directly → BLOCK
- Section Leader using Edit/Write directly → BLOCK
- Only Musicians (subagents) may perform actual file modifications

This enforces the principle from multi-agent-shogun:
"自分でファイルを読み書きしてタスクを実行" is FORBIDDEN for upper agents.
"""

import json
import os
import re
import sys
from pathlib import Path


def get_agent_role() -> str:
    """
    Determine the current agent's role.

    Detection methods:
    1. AGENT_ROLE environment variable (explicit)
    2. Prompt content analysis (implicit)
    3. Default to conductor (main session)
    """
    # Explicit role from environment
    role = os.environ.get("AGENT_ROLE", "").lower()
    if role in ("conductor", "section_leader", "musician"):
        return role

    # Check if we're in a subagent context
    # Subagents typically have hierarchy context in their prompt
    hook_input = os.environ.get("CLAUDE_HOOK_INPUT", "{}")
    try:
        data = json.loads(hook_input)
        # If there's a parent context, we're likely a subagent
        tool_input = data.get("tool_input", {})
        if isinstance(tool_input, dict):
            prompt = tool_input.get("prompt", "")
            if "Role: musician" in prompt or "role: musician" in prompt:
                return "musician"
            if "Role: section_leader" in prompt:
                return "section_leader"
    except (json.JSONDecodeError, AttributeError):
        pass

    # Default: main session is Conductor
    return "conductor"


def is_allowed_file(file_path: str) -> bool:
    """
    Check if the file is allowed to be edited by upper agents.

    Some files are meta/config and can be edited by any agent:
    - .claude/ configuration files
    - Documentation files (*.md in .claude/)
    - Memory files
    """
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


def is_delegation_context() -> bool:
    """
    Check if we're in a delegation context (spawning a subagent).

    If the current operation is part of setting up a subagent,
    we should allow it.
    """
    hook_input = os.environ.get("CLAUDE_HOOK_INPUT", "{}")
    try:
        data = json.loads(hook_input)
        # Check recent tool calls or context
        # This is a heuristic - in practice, we may need more sophisticated detection
        return False
    except (json.JSONDecodeError, AttributeError):
        return False


def main() -> None:
    """Main hook logic."""
    hook_input = os.environ.get("CLAUDE_HOOK_INPUT", "{}")

    try:
        data = json.loads(hook_input)
    except json.JSONDecodeError:
        # Not valid JSON, approve by default
        print(json.dumps({"result": "approve"}))
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only check Edit and Write tools
    if tool_name not in ("Edit", "Write"):
        print(json.dumps({"result": "approve"}))
        return

    # Get file path
    file_path = ""
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")

    # Check if this file is allowed for upper agents
    if is_allowed_file(file_path):
        print(json.dumps({"result": "approve"}))
        return

    # Determine agent role
    role = get_agent_role()

    # Musicians can edit anything (they are the executors)
    if role == "musician":
        print(json.dumps({"result": "approve"}))
        return

    # Conductor and Section Leader should NOT directly edit implementation files
    if role in ("conductor", "section_leader"):
        role_name = "Conductor（指揮者）" if role == "conductor" else "Section Leader（セクションリーダー）"

        message = f"""
⛔ 階層違反: {role_name} は直接ファイルを編集できません。

【禁止事項】
- {role_name} が直接 Edit/Write でコードやファイルを変更すること

【正しい方法】
- Task ツールでサブエージェント（Musician）を spawn して委譲してください

例:
```
Task tool:
- subagent_type: "general-purpose"
- prompt: |
    ## Hierarchy Context
    Parent: {role}
    Role: musician

    ## Task
    {file_path} を編集して...
```

→ 詳細: .claude/rules/agent-hierarchy.md
"""
        print(json.dumps({"result": "block", "message": message}))
        return

    # Unknown role, approve by default
    print(json.dumps({"result": "approve"}))


if __name__ == "__main__":
    main()

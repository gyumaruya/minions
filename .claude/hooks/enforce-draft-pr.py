#!/usr/bin/env python3
"""
PreToolUse hook: Enforce --draft flag for gh pr create.

Blocks PR creation without --draft flag.
"""
from __future__ import annotations

import json
import re
import sys


def main():
    # Read input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    # Check if this is a gh pr create command
    if not re.search(r"\bgh\s+pr\s+create\b", command):
        sys.exit(0)

    # Check if --draft flag is present
    if "--draft" in command:
        sys.exit(0)

    # Block: gh pr create without --draft
    message = """⚠️ PR は必ず --draft で作成してください。

修正: gh pr create --draft ...

理由: レビュー準備が整うまで draft 状態を維持するルールです。"""

    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message
        }
    }, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()

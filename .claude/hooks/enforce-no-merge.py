#!/usr/bin/env python3
"""
PreToolUse hook: Prevent merge operations.

Blocks gh pr merge commands. Merging should be done by users, not agents.
"""
from __future__ import annotations

import json
import sys


def main():
    # Read input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only check Bash tool
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    # Check for merge commands
    if "gh pr merge" in command or "git merge" in command:
        message = """⛔ マージ操作はブロックされています。

【理由】
マージはユーザーが行うべき操作です。

【許可されている操作】
- gh pr ready（レビュー準備完了にする）
- gh pr view（PRを確認する）

【マージ方法】
GitHub UI または以下のコマンドをユーザーが実行:
  gh pr merge <number>"""

        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message
            }
        }, sys.stdout)
        sys.exit(0)

    # Allow other commands
    sys.exit(0)


if __name__ == "__main__":
    main()

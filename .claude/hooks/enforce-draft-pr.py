#!/usr/bin/env python3
"""
PreToolUse hook: Enforce draft PR workflow.

- Blocks PR creation without --draft flag
- Blocks gh pr ready (requires user confirmation)
"""

from __future__ import annotations

import json
import os
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
    if re.search(r"\bgh\s+pr\s+create\b", command):
        # Check if --draft flag is present
        if "--draft" in command:
            sys.exit(0)

        # Block: gh pr create without --draft
        message = """⚠️ PR は必ず --draft で作成してください。

修正: gh pr create --draft ...

理由: レビュー準備が整うまで draft 状態を維持するルールです。"""

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

    # Check if this is a gh pr ready command
    if re.search(r"\bgh\s+pr\s+ready\b", command):
        # Check for explicit bypass flag in environment
        if os.environ.get("ALLOW_PR_READY") == "1":
            sys.exit(0)

        # Block: require user confirmation
        message = """⚠️ PR を ready にしようとしています。

本当にレビュー準備が完了していますか？

- まだ編集が必要な場合: このコマンドをスキップしてください
- 準備完了の場合: ユーザーが明示的に許可してください

/pr-workflow ready を使用するか、手動で gh pr ready を実行してください。"""

        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": message,
                }
            },
            sys.stdout,
        )
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()

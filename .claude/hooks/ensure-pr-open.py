#!/usr/bin/env python3
"""
PreToolUse hook: BLOCK Edit/Write if no open PR exists.

This is a hard enforcement - no PR, no changes allowed.
"""

import json
import subprocess
import sys


def has_any_open_pr() -> bool:
    """Check if there's any open PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        prs = json.loads(result.stdout) if result.stdout else []
        return len(prs) > 0
    except Exception:
        return False


def main():
    # Read input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")

    # Only check Edit and Write tools
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    # Check if any PR is open
    if has_any_open_pr():
        sys.exit(0)

    # No PR open - BLOCK the operation
    message = (
        "⛔ 編集をブロック: オープンなPRがありません。\n\n"
        "セッション開始時に自動でPRが作成されるはずですが、作成に失敗した可能性があります。\n\n"
        "手動で作成してください:\n"
        "1. git push -u origin <branch-name>\n"
        '2. gh pr create --draft --title "WIP: ..." --body "..."\n\n'
        "または新しいセッションを開始してください。"
    )

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


if __name__ == "__main__":
    main()

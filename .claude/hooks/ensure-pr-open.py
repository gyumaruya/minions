#!/usr/bin/env python3
"""
PreToolUse hook: BLOCK Edit/Write if no open PR exists.

This is a hard enforcement - no PR, no changes allowed.
"""

import json
import os
import subprocess
import sys


def has_any_open_pr() -> bool:
    """Check if there's any open PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=10
        )
        prs = json.loads(result.stdout) if result.stdout else []
        return len(prs) > 0
    except Exception:
        return False


def main():
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")

    if not tool_input:
        print(json.dumps({"result": "approve"}))
        return

    # Check if any PR is open
    if has_any_open_pr():
        print(json.dumps({"result": "approve"}))
        return

    # No PR open - BLOCK the operation
    print(
        json.dumps(
            {
                "result": "block",
                "message": (
                    "⛔ 編集をブロック: オープンなPRがありません。\n\n"
                    "セッション開始時に自動でPRが作成されるはずですが、作成に失敗した可能性があります。\n\n"
                    "手動で作成してください:\n"
                    "1. jj git push -c @\n"
                    "2. gh pr create --draft --title \"WIP: ...\" --body \"...\"\n\n"
                    "または新しいセッションを開始してください。"
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PreToolUse hook: Enforce --draft flag for gh pr create.

Blocks PR creation without --draft flag.
"""

import json
import os
import re
import sys


def main():
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")

    if not tool_input:
        print(json.dumps({"result": "approve"}))
        return

    try:
        data = json.loads(tool_input)
        command = data.get("command", "")
    except json.JSONDecodeError:
        print(json.dumps({"result": "approve"}))
        return

    # Check if this is a gh pr create command
    if not re.search(r"\bgh\s+pr\s+create\b", command):
        print(json.dumps({"result": "approve"}))
        return

    # Check if --draft flag is present
    if "--draft" in command:
        print(json.dumps({"result": "approve"}))
        return

    # Block: gh pr create without --draft
    print(
        json.dumps(
            {
                "result": "block",
                "message": "⚠️ PR は必ず --draft で作成してください。\n\n"
                "修正: gh pr create --draft ...\n\n"
                "理由: レビュー準備が整うまで draft 状態を維持するルールです。",
            }
        )
    )


if __name__ == "__main__":
    main()

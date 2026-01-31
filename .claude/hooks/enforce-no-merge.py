#!/usr/bin/env python3
"""
PreToolUse hook: Block gh pr merge commands.

Merge operations should be done by the user, not the agent.
"""

import json
import os
import re


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

    # Check if this is a gh pr merge command
    if re.search(r"\bgh\s+pr\s+merge\b", command):
        print(
            json.dumps(
                {
                    "result": "block",
                    "message": (
                        "⛔ マージ操作はブロックされています。\n\n"
                        "マージはユーザーが行うべき操作です。\n\n"
                        "以下までは実行可能:\n"
                        "- `gh pr ready` (draft 解除)\n"
                        "- `gh pr view` (PR 確認)\n\n"
                        "マージはユーザーが GitHub UI または CLI で実行してください。"
                    ),
                }
            )
        )
        return

    print(json.dumps({"result": "approve"}))


if __name__ == "__main__":
    main()

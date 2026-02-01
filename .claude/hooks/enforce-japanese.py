#!/usr/bin/env python3
"""
PreToolUse hook: Enforce Japanese for user-facing content.

Intercepts gh pr create and git commit to ensure
titles/messages are in Japanese.
"""

from __future__ import annotations

import json
import re
import sys

# Commands that create user-facing content
PR_CREATE_PATTERN = re.compile(r"gh\s+pr\s+create")
COMMIT_PATTERN = re.compile(r"git\s+commit")


def contains_japanese(text: str) -> bool:
    """Check if text contains Japanese characters."""
    japanese_pattern = re.compile(
        r"[\u3040-\u309F]|"  # Hiragana
        r"[\u30A0-\u30FF]|"  # Katakana
        r"[\u4E00-\u9FFF]|"  # Kanji
        r"[\uFF00-\uFFEF]"  # Full-width
    )
    return bool(japanese_pattern.search(text))


def extract_title_or_message(command: str) -> str | None:
    """Extract title/message from command."""
    # gh pr create --title "..."
    title_match = re.search(r'--title\s+["\']([^"\']+)["\']', command)
    if title_match:
        return title_match.group(1)

    # jj describe -m "..." or git commit -m "..."
    msg_match = re.search(r'-m\s+["\']([^"\']+)["\']', command)
    if msg_match:
        return msg_match.group(1)

    return None


def main() -> None:
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

    # Check if this is a PR or commit command
    is_pr_create = PR_CREATE_PATTERN.search(command)
    is_commit = COMMIT_PATTERN.search(command)

    if not (is_pr_create or is_commit):
        sys.exit(0)

    # Extract and check the title/message
    title_or_message = extract_title_or_message(command)

    if title_or_message and not contains_japanese(title_or_message):
        action_type = "PRタイトル" if is_pr_create else "コミットメッセージ"

        message = f"""⚠️ {action_type}は日本語で記述してください。

現在の内容: {title_or_message}

日本語に書き換えて再実行してください。"""

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

    # Allow
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Hook: Enforce Japanese for user-facing content.

Intercepts gh pr create, jj describe, git commit and ensures
titles/messages are in Japanese.
"""

import json
import re
import sys
from pathlib import Path

# Add src to path for memory module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Commands that create user-facing content
PR_CREATE_PATTERN = re.compile(r"gh\s+pr\s+create")
COMMIT_PATTERN = re.compile(r"(jj\s+describe|git\s+commit)")


def contains_japanese(text: str) -> bool:
    """Check if text contains Japanese characters."""
    # Japanese character ranges
    japanese_pattern = re.compile(
        r"[\u3040-\u309F]|"  # Hiragana
        r"[\u30A0-\u30FF]|"  # Katakana
        r"[\u4E00-\u9FFF]|"  # Kanji
        r"[\uFF00-\uFFEF]"   # Full-width
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


def record_learning(content: str) -> None:
    """Record this enforcement as a learning."""
    try:
        from minions.memory import remember_user_preference

        remember_user_preference(
            preference="ユーザー向けコンテンツ（PR、コミット）は日本語で作成する",
            context="Japanese enforcement hook triggered",
        )
    except ImportError:
        pass  # Memory module not available


def main() -> None:
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        print(json.dumps({"continue": True}))
        return

    command = tool_input.get("command", "")

    # Check if this is a PR or commit command
    is_pr_create = PR_CREATE_PATTERN.search(command)
    is_commit = COMMIT_PATTERN.search(command)

    if not (is_pr_create or is_commit):
        print(json.dumps({"continue": True}))
        return

    # Extract and check the title/message
    title_or_message = extract_title_or_message(command)

    if title_or_message and not contains_japanese(title_or_message):
        # Block and request Japanese
        action_type = "PRタイトル" if is_pr_create else "コミットメッセージ"

        result = {
            "continue": False,
            "message": (
                f"⚠️ {action_type}は日本語で記述してください。\n\n"
                f"現在の内容: {title_or_message}\n\n"
                "日本語に書き換えて再実行してください。"
            ),
        }
        print(json.dumps(result, ensure_ascii=False))
        return

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Hook: Auto-learn from user interactions.

Detects learning opportunities from user prompts:
- Corrections: 「〜にして」「違う」「〜じゃない」
- Preferences: 「〜がいい」「〜を使って」
- Workflows: 「いつも〜」「毎回〜」

Saves learnings to memory for self-improvement.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import config utilities
from config_utils import get_openai_api_key

# Correction patterns (Japanese)
CORRECTION_PATTERNS = [
    (r"(.+)にして", "user_correction"),
    (r"(.+)に変えて", "user_correction"),
    (r"(.+)は違う", "user_correction"),
    (r"(.+)じゃない", "user_correction"),
    (r"(.+)ではなく(.+)", "user_correction"),
    (r"(.+)より(.+)がいい", "user_preference"),
    (r"(.+)を使って", "user_preference"),
    (r"(.+)を使わないで", "user_preference"),
    (r"いつも(.+)", "workflow"),
    (r"毎回(.+)", "workflow"),
    (r"常に(.+)", "workflow"),
    (r"覚えて[：:]\s*(.+)", "explicit_learn"),
    (r"記憶して[：:]\s*(.+)", "explicit_learn"),
]

# Memory type mapping
TRIGGER_TO_TYPE = {
    "user_correction": "preference",
    "user_preference": "preference",
    "workflow": "workflow",
    "explicit_learn": "preference",
}


def detect_learning(text: str) -> list[tuple[str, str, str]]:
    """
    Detect learning opportunities in user text.

    Returns list of (content, trigger_type, memory_type) tuples.
    """
    learnings = []

    # Skip questions (ends with ? or の？ etc.)
    if re.search(r"[?？]$|の[?？]$|かな[?？]?$|だい[?？]?$", text.strip()):
        return learnings

    # Skip too long text (likely conversational, not a directive)
    # We use 50 characters as the max directive length to filter out
    # conversational messages and focus on concise user corrections.
    MAX_DIRECTIVE_LENGTH = 50
    if len(text) > MAX_DIRECTIVE_LENGTH:
        return learnings

    for pattern, trigger in CORRECTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            # Extract the full match as learning content
            content = match.group(0)
            memory_type = TRIGGER_TO_TYPE.get(trigger, "preference")
            learnings.append((content, trigger, memory_type))

    return learnings


def save_learning(content: str, memory_type: str, trigger: str) -> bool:
    """Save a learning to memory directly."""
    try:
        from minions.memory import AgentType, MemoryBroker, MemoryScope, MemoryType

        # Try to get API key from Keychain
        api_key = get_openai_api_key()
        enable_mem0 = False

        if api_key:
            # Set environment variable for mem0
            os.environ["OPENAI_API_KEY"] = api_key
            enable_mem0 = True

            # Log to stderr for hook debugging
            print("[auto-learn] mem0 enabled via API key", file=sys.stderr)
        else:
            print(
                "[auto-learn] API key not found, using JSONL fallback",
                file=sys.stderr,
            )

        broker = MemoryBroker(enable_mem0=enable_mem0)
        broker.add(
            content=content,
            memory_type=MemoryType(memory_type),
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
            context=f"auto-learn: {trigger}",
        )
        return True
    except Exception:
        return False


def main() -> None:
    """Main hook entry point."""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Get user prompt
    user_message = hook_input.get("prompt", "")

    if not user_message:
        sys.exit(0)

    # Detect learnings
    learnings = detect_learning(user_message)

    # Save detected learnings (fire and forget)
    saved = 0
    for content, trigger, memory_type in learnings:
        if save_learning(content, memory_type, trigger):
            saved += 1

    # Add system message about learned content
    if saved > 0:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"💡 {saved} 件の学習を記録しました。",
                }
            },
            sys.stdout,
            ensure_ascii=False,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()

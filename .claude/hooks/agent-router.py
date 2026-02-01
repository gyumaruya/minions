#!/usr/bin/env python3
"""
UserPromptSubmit hook: Route to appropriate agent based on user intent.

Priority:
1. Codex - Design, debugging, deep reasoning (important tasks)
2. Gemini - Research, multimodal, large context (specialized tasks)
3. Copilot - Everything else (cost-effective default with subagents)
"""

from __future__ import annotations

import json
import sys
from typing import Optional

# Triggers for Codex (design, debugging, deep reasoning) - HIGH PRIORITY
CODEX_TRIGGERS = {
    "ja": [
        "設計", "どう設計", "アーキテクチャ",
        "なぜ動かない", "エラー", "バグ", "デバッグ",
        "どちらがいい", "比較して", "トレードオフ",
        "実装方法", "どう実装",
        "リファクタリング", "リファクタ",
        "レビュー",
        "考えて", "分析して", "深く",
        "セキュリティ", "パフォーマンス",
    ],
    "en": [
        "design", "architecture", "architect",
        "debug", "error", "bug", "not working", "fails",
        "compare", "trade-off", "tradeoff", "which is better",
        "how to implement", "implementation",
        "refactor", "simplify",
        "review",
        "think", "analyze", "deeply",
        "security", "performance", "optimize",
    ],
}

# Triggers for Gemini (research, multimodal, large context) - SPECIALIZED
GEMINI_TRIGGERS = {
    "ja": [
        "調べて", "リサーチ", "調査",
        "PDF", "動画", "音声", "画像",
        "コードベース全体", "リポジトリ全体",
        "最新", "ドキュメント",
        "ライブラリ", "パッケージ",
        "Web検索", "ググって",
    ],
    "en": [
        "research", "investigate", "look up", "find out",
        "pdf", "video", "audio", "image",
        "entire codebase", "whole repository",
        "latest", "documentation", "docs",
        "library", "package", "framework",
        "web search", "google",
    ],
}

# Tasks that should stay with Claude directly (no delegation needed)
# Note: Limited to jj/git commands, NOT GitHub operations (those go to Copilot)
DIRECT_TASKS = [
    "jj commit", "jj push", "jj status", "jj log", "jj diff",
    "git commit", "git push", "git status", "git log", "git diff",
    "コミットして", "プッシュして",
    "ファイル作成", "ファイル編集",
    "create file", "edit file",
]


def detect_agent(prompt: str) -> tuple[str | None, str]:
    """Detect which agent should handle this prompt.

    Returns:
        A tuple of (agent_name, trigger) where agent_name is one of
        {"direct", "codex", "gemini", "copilot"}, or (None, "") if no
        delegation should occur (short prompts).
    """
    prompt_lower = prompt.lower()

    # Check if this is a direct task (no delegation)
    for task in DIRECT_TASKS:
        if task.lower() in prompt_lower:
            return "direct", task

    # Priority 1: Check Codex triggers (important tasks)
    for triggers in CODEX_TRIGGERS.values():
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                return "codex", trigger

    # Priority 2: Check Gemini triggers (specialized tasks)
    for triggers in GEMINI_TRIGGERS.values():
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                return "gemini", trigger

    # Priority 3: Everything else -> Copilot (cost-effective)
    # Only suggest for non-trivial prompts
    if len(prompt) > 20:
        return "copilot", "general task"

    return None, ""


def main():
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt", "")

        # Skip very short prompts
        if len(prompt) < 10:
            sys.exit(0)

        agent, trigger = detect_agent(prompt)

        if agent == "direct":
            # No suggestion needed
            sys.exit(0)

        elif agent == "codex":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Agent: Codex] Detected '{trigger}' - important task requiring deep reasoning. "
                        "Use Codex for design decisions, debugging, or complex analysis. "
                        "Command: `codex exec --model gpt-5.2-codex --sandbox read-only --full-auto \"...\"` "
                        "(via subagent for large outputs)"
                    )
                }
            }
            print(json.dumps(output))

        elif agent == "gemini":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Agent: Gemini] Detected '{trigger}' - specialized research/multimodal task. "
                        "Use Gemini for research, large context analysis, or multimodal content. "
                        "Command: `gemini -p \"...\" 2>/dev/null` "
                        "(via subagent for large outputs)"
                    )
                }
            }
            print(json.dumps(output))

        elif agent == "copilot":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        "[Agent: Copilot] General task - consider using Copilot CLI for cost-effective "
                        "execution with subagent capabilities. "
                        "Command: `copilot -p \"...\" --model claude-opus-4.5 --allow-all --silent 2>/dev/null` "
                        "(direct call OK for quick tasks)"
                    )
                }
            }
            print(json.dumps(output))

        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()

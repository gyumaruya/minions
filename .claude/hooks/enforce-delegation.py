#!/usr/bin/env python3
"""
PreToolUse hook: Enforce delegation for Conductor.

2-tier hierarchy: Conductor delegates to Musician.
Counts work tool usage without delegation and warns/blocks after thresholds.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

WORK_TOOLS = {"Edit", "Write", "Read", "Bash", "WebFetch", "WebSearch"}
DELEGATION_TOOL = "Task"

# Thresholds are tuned to nudge the Conductor towards healthy delegation
# habits without being overly punitive:
# - 3 warnings for the Conductor: allows a few mistakes / exploratory actions
#   while still providing repeated, clear feedback when work tools are used
#   directly instead of delegating.
# - Block after 5 non-delegated work-tool uses within the window: provides a
#   hard stop if warnings are ignored, but is high enough to avoid blocking on
#   occasional edge cases or one-off needs.
WARN_THRESHOLD = {"conductor": 3}
BLOCK_THRESHOLD = {"conductor": 5}

# Use a 10-minute sliding window so that enforcement focuses on recent
# behavior within a typical task burst. This avoids "remembering" older
# misuses across an entire long session while still catching short-term
# patterns of avoiding delegation.
WINDOW_SECONDS = 600  # 10 minutes


def get_session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID", str(os.getppid()))


def get_role() -> str:
    """Determine agent role based on session marker and PPID."""
    # 1. Environment variable takes priority
    role = os.environ.get("AGENT_ROLE", "").lower()
    if role in ("conductor", "musician"):
        return role

    # 2. Check file marker and PPID
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    marker_path = Path(project_dir) / ".claude" / ".conductor-session"
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("ppid") == os.getppid():
                return "conductor"  # Main session
        except Exception:
            pass

    # 3. Default: Musician (subagent)
    return "musician"


def state_path(role: str) -> Path:
    session_id = get_session_id()
    return Path("/tmp") / f"claude-delegation-{session_id}-{role}.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "last_delegation_ts": 0,
            "non_delegate_count": 0,
            "last_warning_at": 0,
            "window_start_ts": 0,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_delegation_ts": 0,
            "non_delegate_count": 0,
            "last_warning_at": 0,
            "window_start_ts": 0,
        }


def save_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def is_allowed_path(file_path: str) -> bool:
    """Check if path is in allowlist for Conductor."""
    path = Path(file_path)
    # .claude/ directory is always allowed
    if ".claude" in path.parts:
        return True
    # memory/ directory is always allowed
    if "memory" in path.parts:
        return True
    # Specific config files are allowed
    return path.name in ("pyproject.toml", "settings.json", ".gitignore")


def is_delegation(tool_input: dict[str, Any]) -> bool:
    """Check if Task call is a delegation to lower hierarchy."""
    prompt = tool_input.get("prompt", "")
    prompt_lower = prompt.lower()
    # Check for hierarchy keywords (musician only in 2-tier system)
    if "musician" in prompt_lower:
        return True
    # Check for subagent_type (always counts as delegation)
    if tool_input.get("subagent_type"):
        return True
    return False


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    role = get_role()

    # Musicians have no restrictions
    if role == "musician":
        sys.exit(0)

    state_file = state_path(role)
    state = load_state(state_file)
    now = int(time.time())

    # Reset window if expired (10 minutes)
    if state["window_start_ts"] and now - state["window_start_ts"] > WINDOW_SECONDS:
        state["non_delegate_count"] = 0
        state["window_start_ts"] = now

    # Handle delegation (Task tool with proper hierarchy)
    if tool_name == DELEGATION_TOOL and is_delegation(tool_input):
        state["last_delegation_ts"] = now
        state["non_delegate_count"] = 0
        state["window_start_ts"] = now
        save_state(state_file, state)
        sys.exit(0)

    # Handle work tools
    if tool_name in WORK_TOOLS:
        # Check allowlist for Edit/Write/Read
        if tool_name in ("Edit", "Write", "Read"):
            file_path = tool_input.get("file_path", "")
            if file_path and is_allowed_path(file_path):
                sys.exit(0)

        # Initialize window if needed
        if state["window_start_ts"] == 0:
            state["window_start_ts"] = now

        state["non_delegate_count"] += 1

        warn_at = WARN_THRESHOLD.get(role, 3)
        block_at = BLOCK_THRESHOLD.get(role, 5)

        # Block if over threshold
        if state["non_delegate_count"] >= block_at:
            message = (
                f"⛔ 階層違反: {role} は直接作業を継続できません。\n"
                f"連続 {state['non_delegate_count']} 回の作業ツール使用。\n"
                "Task ツールで下位エージェント（musician）へ委譲してください。\n"
                f"リセット: python .claude/scripts/reset-delegation.py"
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
                ensure_ascii=False,
            )
            save_state(state_file, state)
            sys.exit(0)

        # Always remind about delegation on every work tool use
        reminder = f"💡 委譲推奨: Task ツールで musician へ委譲できます。（{state['non_delegate_count']}/{block_at}）"

        # Add stronger warning if approaching threshold
        if state["non_delegate_count"] >= warn_at:
            if state["last_warning_at"] < state["non_delegate_count"]:
                state["last_warning_at"] = state["non_delegate_count"]
                reminder = (
                    f"⚠ 委譲なし作業が {state['non_delegate_count']} 回です（{block_at}回でブロック）。\n"
                    "Task ツールで委譲を検討してください。"
                )

        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": reminder,
                }
            },
            sys.stdout,
            ensure_ascii=False,
        )

    save_state(state_file, state)
    sys.exit(0)


if __name__ == "__main__":
    main()

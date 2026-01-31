#!/usr/bin/env python3
"""
PostToolUse hook: Suggest or trigger auto-commit after successful verification.

Triggers when:
- Test commands pass (pytest, npm test, etc.)
- Verification commands succeed (copilot, codex, gemini tests)
- Explicit verification phrases detected
"""

import json
import os
import sys

# Commands that indicate successful verification
VERIFICATION_COMMANDS = [
    "pytest",
    "npm test",
    "npm run test",
    "uv run pytest",
    "poe test",
    "poe all",
    "ruff check",
    "ty check",
]

# Commands that indicate successful agent verification
AGENT_VERIFICATION_PATTERNS = [
    "copilot -p",
    "codex exec",
    "gemini -p",
]

# Output patterns indicating success
SUCCESS_PATTERNS = [
    "passed",
    "ok",
    "success",
    "✓",
    "✅",
]

# Output patterns indicating failure
FAILURE_PATTERNS = [
    "failed",
    "error",
    "❌",
    "FAILED",
    "ERROR",
]


def is_verification_command(command: str) -> bool:
    """Check if command is a verification command."""
    command_lower = command.lower()
    for vc in VERIFICATION_COMMANDS:
        if vc in command_lower:
            return True
    for pattern in AGENT_VERIFICATION_PATTERNS:
        if pattern in command_lower:
            return True
    return False


def is_successful(output: str, exit_code: int) -> bool:
    """Check if the command output indicates success."""
    if exit_code != 0:
        return False

    output_lower = output.lower()

    # Check for failure patterns first
    for pattern in FAILURE_PATTERNS:
        if pattern.lower() in output_lower:
            return False

    # If exit code is 0 and no failure patterns, consider it success
    return True


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes in jj."""
    try:
        import subprocess
        result = subprocess.run(
            ["jj", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # If status shows changes, return True
        return "Working copy changes" in result.stdout or "Modified" in result.stdout
    except Exception:
        return False


def main():
    try:
        data = json.load(sys.stdin)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        tool_result = data.get("tool_result", {})

        # Only process Bash commands
        if tool_name != "Bash":
            sys.exit(0)

        command = tool_input.get("command", "")
        output = tool_result.get("stdout", "") or tool_result.get("output", "")
        exit_code = tool_result.get("exit_code", 0)

        # Check if this is a verification command
        if not is_verification_command(command):
            sys.exit(0)

        # Check if it was successful
        if not is_successful(output, exit_code):
            sys.exit(0)

        # Check if there are uncommitted changes
        if not has_uncommitted_changes():
            sys.exit(0)

        # Suggest auto-commit
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "[Auto-Commit Ready] Verification passed with uncommitted changes. "
                    "Consider committing: "
                    "`jj describe -m \"...\" && jj bookmark set main -r @ && jj git push`"
                )
            }
        }
        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()

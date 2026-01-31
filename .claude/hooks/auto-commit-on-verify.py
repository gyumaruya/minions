#!/usr/bin/env python3
"""
PostToolUse hook: Auto-push after successful verification when PR is open.

Triggers when:
- Test commands pass (pytest, npm test, etc.)
- Verification commands succeed (copilot, codex, gemini tests)
- Explicit verification phrases detected

If a PR is open, automatically pushes without asking permission.
"""

import json
import subprocess
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


def get_current_branch() -> str | None:
    """Get the current feature branch name."""
    try:
        result = subprocess.run(
            ["jj", "bookmark", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in result.stdout.split("\n"):
            if "feature/" in line and "@origin" not in line and "*" in line:
                parts = line.split(":")
                if parts:
                    return parts[0].strip().rstrip("*").strip()
        return None
    except Exception:
        return None


def has_open_pr() -> bool:
    """Check if there's an open PR for any feature branch."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number,headRefName"],
            capture_output=True,
            text=True,
            timeout=10
        )
        prs = json.loads(result.stdout) if result.stdout else []
        return len(prs) > 0
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

        # Check if PR is open - if so, auto-push without asking
        if has_open_pr():
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "[Auto-Push] PR is open. Verification passed with uncommitted changes. "
                        "Push automatically: `jj describe -m \"...\" && jj git push`"
                    )
                }
            }
        else:
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "[PR Required] No open PR. Create feature branch and PR first: "
                        "`jj git push -c @ && gh pr create --draft`"
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

#!/usr/bin/env python3
"""
Hook: Ensure noreply email is used for git/jj commits.

Runs before jj/git commands to ensure the correct email is configured.
"""

from __future__ import annotations

import json
import subprocess
import sys

NOREPLY_EMAIL = "gyumaruya@users.noreply.github.com"


def get_current_email() -> str | None:
    """Get current email config for git."""
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def set_email() -> None:
    """Set email to noreply for git (repo-local config)."""
    try:
        subprocess.run(
            ["git", "config", "user.email", NOREPLY_EMAIL],
            capture_output=True,
            timeout=2,
        )
    except Exception as e:
        # Best-effort: don't block the hook if setting the email fails
        print(f"Warning: failed to set git email to noreply: {e}", file=sys.stderr)


def main() -> None:
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only process Bash commands
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    # Check if it's a git command that might commit
    is_git_commit = command.startswith("git ") and any(
        kw in command for kw in ["commit", "push"]
    )

    if not is_git_commit:
        sys.exit(0)

    # Check and fix email if needed
    current_email = get_current_email()

    # Set email if missing or different from noreply
    if current_email is None or current_email != NOREPLY_EMAIL:
        set_email()

    # Allow the command
    sys.exit(0)


if __name__ == "__main__":
    main()

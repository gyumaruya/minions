#!/usr/bin/env python3
"""
Hook: Ensure noreply email is used for git/jj commits.

Runs before jj/git commands to ensure the correct email is configured.
"""

import json
import subprocess
import sys

NOREPLY_EMAIL = "gyumaruya@users.noreply.github.com"


def get_current_email(tool: str) -> str | None:
    """Get current email config for jj or git."""
    try:
        if tool == "jj":
            result = subprocess.run(
                ["jj", "config", "get", "user.email"],
                capture_output=True,
                text=True,
                timeout=2,
            )
        else:
            result = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True,
                text=True,
                timeout=2,
            )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def set_email(tool: str) -> None:
    """Set email to noreply for jj or git (repo-local config)."""
    try:
        if tool == "jj":
            subprocess.run(
                ["jj", "config", "set", "--repo", "user.email", NOREPLY_EMAIL],
                capture_output=True,
                timeout=2,
            )
        else:
            # Use repo-local config instead of --global
            subprocess.run(
                ["git", "config", "user.email", NOREPLY_EMAIL],
                capture_output=True,
                timeout=2,
            )
    except Exception as e:
        # Best-effort: don't block the hook if setting the email fails
        print(f"Warning: failed to set {tool} email to noreply: {e}", file=sys.stderr)


def main() -> None:
    # Read hook input safely; default to allowing the call on parse failures
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"continue": True}))
            return
        hook_input = json.loads(raw_input)
    except json.JSONDecodeError:
        print(json.dumps({"continue": True}))
        return
    except Exception:
        print(json.dumps({"continue": True}))
        return

    if not isinstance(hook_input, dict):
        print(json.dumps({"continue": True}))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only process Bash commands
    if tool_name != "Bash":
        print(json.dumps({"continue": True}))
        return

    command = tool_input.get("command", "")

    # Check if it's a jj or git command that might commit
    is_jj_commit = command.startswith("jj ") and any(
        kw in command for kw in ["commit", "describe", "new", "push", "git push"]
    )
    is_git_commit = command.startswith("git ") and any(
        kw in command for kw in ["commit", "push"]
    )

    if not (is_jj_commit or is_git_commit):
        print(json.dumps({"continue": True}))
        return

    # Check and fix email if needed
    tool = "jj" if is_jj_commit else "git"
    current_email = get_current_email(tool)

    # Set email if missing or different from noreply
    if current_email is None or current_email != NOREPLY_EMAIL:
        set_email(tool)
        # Also set git email for jj (uses git backend)
        if tool == "jj":
            set_email("git")

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()

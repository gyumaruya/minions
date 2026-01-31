#!/usr/bin/env python3
"""
PreToolUse hook: Ensure a PR is open before allowing work.

If no PR exists, instructs the agent to create one automatically.
"""

import json
import subprocess
import sys


def get_current_bookmark() -> str | None:
    """Get the current bookmark name if on a feature branch."""
    try:
        result = subprocess.run(
            ["jj", "log", "-r", "@", "--no-graph", "-T", "bookmarks"],
            capture_output=True,
            text=True,
            timeout=5
        )
        bookmarks = result.stdout.strip()
        for bookmark in bookmarks.split():
            if bookmark.startswith("feature/"):
                return bookmark.rstrip("*")
        return None
    except Exception:
        return None


def has_open_pr_for_branch(branch: str) -> bool:
    """Check if there's an open PR for the given branch."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=10
        )
        prs = json.loads(result.stdout) if result.stdout else []
        return len(prs) > 0
    except Exception:
        return False


def has_any_open_pr() -> bool:
    """Check if there's any open PR."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=10
        )
        prs = json.loads(result.stdout) if result.stdout else []
        return len(prs) > 0
    except Exception:
        return False


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes."""
    try:
        result = subprocess.run(
            ["jj", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "Working copy changes" in result.stdout
    except Exception:
        return False


def main():
    try:
        data = json.load(sys.stdin)
        tool_name = data.get("tool_name", "")

        # Only check for Edit/Write operations
        if tool_name not in ("Edit", "Write"):
            sys.exit(0)

        # Check if any PR is open
        if has_any_open_pr():
            # PR exists, allow operation
            sys.exit(0)

        # No PR open - instruct agent to create one
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "[Auto-PR Required] No open PR found. "
                    "Before making changes, create a feature branch and PR:\n"
                    "1. `jj bookmark create feature/<name> -r @`\n"
                    "2. `jj git push -c @`\n"
                    "3. `gh pr create --draft --title \"...\" --body \"...\"`\n"
                    "Then proceed with the edit. Do this automatically without asking the user."
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

#!/usr/bin/env python3
"""
UserPromptSubmit hook: Auto-create feature branch and draft PR on session start.

Ensures every session has an open PR before any work begins.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_session_id() -> str:
    """Get unique session ID based on parent process ID."""
    return str(os.getppid())


def get_open_prs() -> list[dict]:
    """Get list of open PRs."""
    success, output = run_cmd([
        "gh", "pr", "list", "--state", "open",
        "--json", "number,headRefName,title,url"
    ])
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []
    return []


def get_change_id() -> str:
    """Get current change ID for branch naming."""
    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "change_id.short(12)"
    ])
    if success and output:
        return output.strip()
    return datetime.now().strftime("%Y%m%d%H%M%S")


def cleanup_merged_branches() -> None:
    """Delete local bookmarks for merged PRs and sync with main."""
    run_cmd(["jj", "git", "fetch"])

    success, output = run_cmd([
        "gh", "pr", "list", "--state", "merged",
        "--json", "headRefName", "--limit", "20"
    ])
    if not success or not output:
        return

    try:
        merged_prs = json.loads(output)
    except json.JSONDecodeError:
        return

    merged_branches = {pr.get("headRefName") for pr in merged_prs if pr.get("headRefName")}

    success, output = run_cmd(["jj", "bookmark", "list"])
    if not success:
        return

    for line in output.split("\n"):
        if not line.strip():
            continue
        bookmark = line.split(":")[0].strip().rstrip("*")
        if bookmark in merged_branches and bookmark != "main":
            # Forget the bookmark (removes local tracking without affecting remote)
            run_cmd(["jj", "bookmark", "forget", bookmark])

    run_cmd(["jj", "rebase", "-d", "main@origin"])


def sync_bookmark_with_pr(branch_name: str) -> bool:
    """
    Sync local bookmark with existing PR branch.

    This ensures the local bookmark points to current commit and tracks the remote.
    Prevents the "bookmark deleted" problem that causes PR recreation.
    """
    # Step 1: Set local bookmark to current commit (creates if doesn't exist)
    success, _ = run_cmd(["jj", "bookmark", "set", branch_name, "-r", "@"])
    if not success:
        # Try create if set fails
        run_cmd(["jj", "bookmark", "create", branch_name, "-r", "@"])

    # Step 2: Track the remote bookmark (links local to remote)
    run_cmd(["jj", "bookmark", "track", branch_name, "--remote=origin"])

    # Step 3: Push to update the remote (with tracking, this updates instead of deletes)
    success, output = run_cmd([
        "jj", "git", "push", "--bookmark", branch_name
    ])

    return success


def create_branch_and_pr() -> tuple[bool, str, str]:
    """Create a new feature branch and draft PR."""
    change_id = get_change_id()
    branch_name = f"feature/session-{change_id}"

    run_cmd(["jj", "describe", "-m", f"WIP: Session {change_id}"])

    # Step 1: Create or set bookmark
    success, _ = run_cmd(["jj", "bookmark", "create", branch_name, "-r", "@"])
    if not success:
        run_cmd(["jj", "bookmark", "set", branch_name, "-r", "@"])

    # Step 2: Push with --allow-new for new branches
    success, output = run_cmd([
        "jj", "git", "push", "--bookmark", branch_name, "--allow-new"
    ])
    if not success:
        return False, f"Failed to push: {output}", ""

    # Step 3: Track the remote bookmark to prevent future sync issues
    run_cmd(["jj", "bookmark", "track", branch_name, "--remote=origin"])

    # Step 4: Create the PR
    success, output = run_cmd([
        "gh", "pr", "create", "--draft",
        "--head", branch_name, "--base", "main",
        "--title", f"WIP: Session {change_id}",
        "--body", "🤖 Auto-created draft PR for session."
    ])

    if success:
        pr_url = output.strip().split("\n")[-1] if output else ""
        return True, branch_name, pr_url
    return False, f"Failed to create PR: {output}", ""


def is_marker_valid(marker_file: str, session_id: str) -> bool:
    """Check if marker file is valid for current session."""
    if not os.path.exists(marker_file):
        return False
    try:
        with open(marker_file, "r") as f:
            content = f.read().strip()
            if ":" in content:
                stored_session = content.split(":")[0]
                return stored_session == session_id
            return False
    except Exception:
        return False


def write_marker(marker_file: str, session_id: str, pr_info: str) -> None:
    """Write session marker file."""
    try:
        with open(marker_file, "w") as f:
            f.write(f"{session_id}:{pr_info}")
    except Exception:
        pass


def main():
    # Read input from stdin (correct way)
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        hook_input = {}

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    marker_file = os.path.join(project_dir, ".claude", ".session-pr-created")
    session_id = get_session_id()

    # Skip if marker exists AND is for current session
    if is_marker_valid(marker_file, session_id):
        sys.exit(0)

    # New session - delete old marker
    if os.path.exists(marker_file):
        try:
            os.remove(marker_file)
        except Exception:
            pass

    # Cleanup merged branches
    cleanup_merged_branches()

    # Check for existing open PR
    open_prs = get_open_prs()
    if open_prs:
        pr = open_prs[0]
        pr_branch = pr.get("headRefName", "")
        pr_number = pr.get("number", "")
        pr_url = pr.get("url", "")

        # IMPORTANT: Sync local bookmark with the PR branch
        # This prevents the "bookmark deleted" problem that closes PRs
        if pr_branch:
            sync_bookmark_with_pr(pr_branch)

        write_marker(marker_file, session_id, f"existing:{pr_branch}:#{pr_number}")

        # Output additional context for Claude
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"📋 既存のPR #{pr_number} を使用（ブックマーク同期済み）: {pr_url}"
            }
        }, sys.stdout)
        sys.exit(0)

    # No open PR - create one
    success, message, pr_url = create_branch_and_pr()

    if success:
        write_marker(marker_file, session_id, f"created:{message}")
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"✅ Draft PR を自動作成: {pr_url}"
            }
        }, sys.stdout)
    else:
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"⚠️ PR自動作成に失敗: {message}"
            }
        }, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()

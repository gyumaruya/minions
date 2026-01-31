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
from typing import Optional


def run_cmd(cmd: "list[str]", timeout: int = 30) -> "tuple[bool, str]":
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_open_prs() -> "list[dict]":
    """Get list of open PRs."""
    success, output = run_cmd([
        "gh", "pr", "list", "--state", "open",
        "--json", "number,headRefName,title"
    ])
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []
    return []


def get_current_bookmark() -> Optional[str]:
    """Get current bookmark name."""
    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "bookmarks"
    ])
    if success and output:
        # Return first non-main bookmark
        for bookmark in output.split():
            bookmark = bookmark.rstrip("*")
            if bookmark and bookmark != "main":
                return bookmark
    return None


def is_on_main() -> bool:
    """Check if current commit is on main."""
    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "bookmarks"
    ])
    if success:
        bookmarks = output.strip().replace("*", "").split()
        return "main" in bookmarks or not bookmarks
    return True


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
    # Fetch latest from remote
    run_cmd(["jj", "git", "fetch"])

    # Get list of merged PRs
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

    # Get local bookmarks
    success, output = run_cmd(["jj", "bookmark", "list"])
    if not success:
        return

    # Delete local bookmarks that correspond to merged PRs
    for line in output.split("\n"):
        if not line.strip():
            continue
        bookmark = line.split(":")[0].strip().rstrip("*")
        if bookmark in merged_branches and bookmark != "main":
            run_cmd(["jj", "bookmark", "delete", bookmark])

    # Rebase to latest main
    run_cmd(["jj", "rebase", "-d", "main@origin"])

    # Abandon empty commits
    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "empty"
    ])
    if success and output.strip() == "true":
        run_cmd(["jj", "abandon", "@"])


def create_branch_and_pr() -> "tuple[bool, str]":
    """Create a new feature branch and draft PR."""
    change_id = get_change_id()
    branch_name = f"feature/session-{change_id}"

    # Add commit description first (required for push)
    run_cmd(["jj", "describe", "-m", f"WIP: Session {change_id}"])

    # Create bookmark
    success, _ = run_cmd(["jj", "bookmark", "create", branch_name, "-r", "@"])
    if not success:
        # Bookmark might exist, try to set it
        run_cmd(["jj", "bookmark", "set", branch_name, "-r", "@"])

    # Push with --allow-new
    success, output = run_cmd([
        "jj", "git", "push", "--bookmark", branch_name, "--allow-new"
    ])
    if not success:
        return False, f"Failed to push: {output}"

    # Create draft PR
    success, output = run_cmd([
        "gh", "pr", "create",
        "--draft",
        "--head", branch_name,
        "--base", "main",
        "--title", f"WIP: Session {change_id}",
        "--body", "🤖 Auto-created draft PR for session.\n\nThis PR was automatically created to track changes in this session."
    ])

    if success:
        # Extract PR URL from output
        pr_url = output.strip().split("\n")[-1] if output else ""
        return True, f"Created: {branch_name} → {pr_url}"
    else:
        return False, f"Failed to create PR: {output}"


def main():
    # Check for marker file to avoid creating multiple PRs in same session
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    marker_file = os.path.join(project_dir, ".claude", ".session-pr-created")

    # Skip if marker exists (PR already created this session)
    if os.path.exists(marker_file):
        print(json.dumps({"result": "approve"}))
        return

    # First session action: cleanup merged branches
    cleanup_merged_branches()

    # Check if there's already an open PR
    open_prs = get_open_prs()
    if open_prs:
        # Touch marker file
        try:
            with open(marker_file, "w") as f:
                f.write(open_prs[0].get("headRefName", ""))
        except Exception:
            pass
        print(json.dumps({"result": "approve"}))
        return

    # No open PR - create one automatically
    success, message = create_branch_and_pr()

    if success:
        # Touch marker file
        try:
            with open(marker_file, "w") as f:
                f.write(message)
        except Exception:
            pass

        # Return success with info
        print(json.dumps({
            "result": "approve",
            "message": f"✅ Auto-created draft PR: {message}"
        }))
    else:
        # Failed to create, but don't block - just warn
        print(json.dumps({
            "result": "approve",
            "message": f"⚠️ Failed to auto-create PR: {message}\nPlease create manually."
        }))


if __name__ == "__main__":
    main()

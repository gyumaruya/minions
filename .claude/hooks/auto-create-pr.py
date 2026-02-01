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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_session_id() -> str:
    """Get unique session ID based on parent process ID."""
    return str(os.getppid())


def get_open_prs() -> list[dict]:
    """Get list of open PRs."""
    success, output = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,headRefName,title,url",
        ]
    )
    if success and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []
    return []


def get_short_hash() -> str:
    """Get current commit short hash for branch naming."""
    success, output = run_cmd(["git", "rev-parse", "--short", "HEAD"])
    if success and output:
        return output.strip()
    return datetime.now().strftime("%Y%m%d%H%M%S")


def cleanup_merged_branches() -> None:
    """Delete local branches for merged PRs and sync with main."""
    run_cmd(["git", "fetch", "origin"])

    success, output = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "merged",
            "--json",
            "headRefName",
            "--limit",
            "20",
        ]
    )
    if not success or not output:
        return

    try:
        merged_prs = json.loads(output)
    except json.JSONDecodeError:
        return

    merged_branches = {
        pr.get("headRefName") for pr in merged_prs if pr.get("headRefName")
    }

    success, output = run_cmd(["git", "branch"])
    if not success:
        return

    for line in output.split("\n"):
        branch = line.strip().lstrip("* ").strip()
        if branch in merged_branches and branch != "main":
            run_cmd(["git", "branch", "-D", branch])

    # Sync with main
    run_cmd(["git", "checkout", "main"])
    run_cmd(["git", "pull", "origin", "main"])


def sync_branch_with_pr(branch_name: str) -> bool:
    """
    Sync local branch with existing PR branch.

    Ensures local branch is up-to-date with remote.
    """
    # Fetch latest
    run_cmd(["git", "fetch", "origin", branch_name])

    # Checkout or create tracking branch
    success, _ = run_cmd(["git", "checkout", branch_name])
    if not success:
        # Create tracking branch
        run_cmd(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"])

    # Pull latest changes
    success, _ = run_cmd(["git", "pull", "origin", branch_name])

    return success


def create_branch_and_pr() -> tuple[bool, str, str]:
    """Create a new feature branch and draft PR."""
    short_hash = get_short_hash()
    branch_name = f"feature/session-{short_hash}"

    # Create new branch from main
    run_cmd(["git", "checkout", "main"])
    success, _ = run_cmd(["git", "checkout", "-b", branch_name])
    if not success:
        return False, f"Failed to create branch: {branch_name}", ""

    # Create initial commit if needed
    success, output = run_cmd(["git", "status", "--porcelain"])
    if success and output.strip():
        # There are uncommitted changes - commit them
        run_cmd(["git", "add", "-A"])
        run_cmd(
            [
                "git",
                "commit",
                "-m",
                f"WIP: Session {short_hash}\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>",
            ]
        )

    # Push branch
    success, output = run_cmd(["git", "push", "-u", "origin", branch_name])
    if not success:
        return False, f"Failed to push: {output}", ""

    # Create PR
    success, output = run_cmd(
        [
            "gh",
            "pr",
            "create",
            "--draft",
            "--head",
            branch_name,
            "--base",
            "main",
            "--title",
            f"WIP: Session {short_hash}",
            "--body",
            "🤖 Auto-created draft PR for session.",
        ]
    )

    if success:
        pr_url = output.strip().split("\n")[-1] if output else ""
        return True, branch_name, pr_url
    return False, f"Failed to create PR: {output}", ""


def is_marker_valid(marker_file: str, session_id: str) -> bool:
    """Check if marker file is valid for current session."""
    if not os.path.exists(marker_file):
        return False
    try:
        with open(marker_file) as f:
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


def create_conductor_marker(project_dir: str) -> None:
    """Create conductor session marker with PPID."""
    from pathlib import Path

    marker_path = Path(project_dir) / ".claude" / ".conductor-session"
    marker_data = {"ppid": os.getppid(), "created_at": datetime.now().isoformat()}
    marker_path.write_text(json.dumps(marker_data), encoding="utf-8")


def main():
    # Read input from stdin (correct way)
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    marker_file = os.path.join(project_dir, ".claude", ".session-pr-created")
    session_id = get_session_id()

    # Create conductor marker at session start
    create_conductor_marker(project_dir)

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

        # Sync local branch with the PR branch
        if pr_branch:
            sync_branch_with_pr(pr_branch)

        write_marker(marker_file, session_id, f"existing:{pr_branch}:#{pr_number}")

        # Output additional context for Claude
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"📋 既存のPR #{pr_number} を使用（ブランチ同期済み）: {pr_url}",
                }
            },
            sys.stdout,
        )
        sys.exit(0)

    # No open PR - create one
    success, message, pr_url = create_branch_and_pr()

    if success:
        write_marker(marker_file, session_id, f"created:{message}")
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"✅ Draft PR を自動作成: {pr_url}",
                }
            },
            sys.stdout,
        )
    else:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"⚠️ PR自動作成に失敗: {message}",
                }
            },
            sys.stdout,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()

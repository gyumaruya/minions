#!/usr/bin/env python3
"""
UserPromptSubmit hook: Auto-create feature branch and draft PR on session start.

Ensures every session has an open PR before any work begins.

IMPORTANT: Uses PPID (parent process ID) to track sessions. Each new Claude Code
session has a different PPID, so the marker file is session-specific.

NOTIFICATION: Writes status to .claude/.pr-status for Claude to read and report.
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


def get_session_id() -> str:
    """Get unique session ID based on parent process ID."""
    return str(os.getppid())


def get_open_prs() -> "list[dict]":
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


def get_current_bookmark() -> Optional[str]:
    """Get current bookmark name."""
    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "bookmarks"
    ])
    if success and output:
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
            run_cmd(["jj", "bookmark", "delete", bookmark])

    run_cmd(["jj", "rebase", "-d", "main@origin"])

    success, output = run_cmd([
        "jj", "log", "-r", "@", "--no-graph", "-T", "empty"
    ])
    if success and output.strip() == "true":
        run_cmd(["jj", "abandon", "@"])


def create_branch_and_pr() -> "tuple[bool, str, str]":
    """Create a new feature branch and draft PR. Returns (success, message, url)."""
    change_id = get_change_id()
    branch_name = f"feature/session-{change_id}"

    run_cmd(["jj", "describe", "-m", f"WIP: Session {change_id}"])

    success, _ = run_cmd(["jj", "bookmark", "create", branch_name, "-r", "@"])
    if not success:
        run_cmd(["jj", "bookmark", "set", branch_name, "-r", "@"])

    success, output = run_cmd([
        "jj", "git", "push", "--bookmark", branch_name, "--allow-new"
    ])
    if not success:
        return False, f"Failed to push: {output}", ""

    success, output = run_cmd([
        "gh", "pr", "create",
        "--draft",
        "--head", branch_name,
        "--base", "main",
        "--title", f"WIP: Session {change_id}",
        "--body", "🤖 Auto-created draft PR for session.\n\nThis PR was automatically created to track changes in this session."
    ])

    if success:
        pr_url = output.strip().split("\n")[-1] if output else ""
        return True, f"{branch_name}", pr_url
    else:
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


def write_status(project_dir: str, status: dict) -> None:
    """Write PR status for Claude to read and report."""
    status_file = os.path.join(project_dir, ".claude", ".pr-status")
    try:
        with open(status_file, "w") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    marker_file = os.path.join(project_dir, ".claude", ".session-pr-created")
    session_id = get_session_id()

    # Skip if marker exists AND is for current session
    if is_marker_valid(marker_file, session_id):
        print(json.dumps({"result": "approve"}))
        return

    # New session - delete old marker if exists
    if os.path.exists(marker_file):
        try:
            os.remove(marker_file)
        except Exception:
            pass

    # First session action: cleanup merged branches
    cleanup_merged_branches()

    # Check if there's already an open PR
    open_prs = get_open_prs()
    if open_prs:
        pr = open_prs[0]
        pr_branch = pr.get("headRefName", "")
        pr_number = pr.get("number", "")
        pr_url = pr.get("url", "")

        write_marker(marker_file, session_id, f"existing:{pr_branch}:#{pr_number}")

        # Write status for Claude to read
        write_status(project_dir, {
            "action": "existing",
            "pr_number": pr_number,
            "branch": pr_branch,
            "url": pr_url,
            "message": f"📋 既存のPR #{pr_number} を使用: {pr_url}"
        })

        print(json.dumps({
            "result": "approve",
            "message": f"📋 既存のPR #{pr_number} ({pr_branch}) を使用します: {pr_url}"
        }))
        return

    # No open PR - create one automatically
    success, message, pr_url = create_branch_and_pr()

    if success:
        write_marker(marker_file, session_id, f"created:{message}")

        # Write status for Claude to read
        write_status(project_dir, {
            "action": "created",
            "branch": message,
            "url": pr_url,
            "message": f"✅ Draft PR を自動作成: {pr_url}"
        })

        print(json.dumps({
            "result": "approve",
            "message": f"✅ Draft PR を自動作成しました: {message} → {pr_url}"
        }))
    else:
        # Write failure status
        write_status(project_dir, {
            "action": "failed",
            "error": message,
            "message": f"⚠️ PR自動作成に失敗: {message}"
        })

        print(json.dumps({
            "result": "approve",
            "message": f"⚠️ PR自動作成に失敗: {message}\n手動で作成してください。"
        }))


if __name__ == "__main__":
    main()

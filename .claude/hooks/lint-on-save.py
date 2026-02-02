#!/usr/bin/env python3
from __future__ import annotations

"""
Post-tool hook: Run formatter and type checker on Python files after Edit/Write.

Triggered after Edit or Write tools modify files.
Runs ruff (format + lint) and ty (type check) on Python files.
"""

import json
import os
import subprocess
import sys

# Input validation constants
MAX_PATH_LENGTH = 4096


def validate_path(file_path: str) -> bool:
    """Validate file path for security."""
    if not file_path or len(file_path) > MAX_PATH_LENGTH:
        return False
    # Check for path traversal
    if ".." in file_path:
        return False
    return True


def get_file_path_from_stdin() -> str | None:
    """Extract file path from hook input via stdin."""
    try:
        hook_input = json.load(sys.stdin)
        tool_input = hook_input.get("tool_input", {})
        return tool_input.get("file_path") if isinstance(tool_input, dict) else None
    except (json.JSONDecodeError, Exception):
        return None


def is_python_file(path: str) -> bool:
    """Check if the file is a Python file."""
    return path.endswith(".py")


def run_command(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def main() -> None:
    file_path = get_file_path_from_stdin()
    if not file_path:
        sys.exit(0)

    # Validate input
    if not validate_path(file_path):
        sys.exit(0)

    if not is_python_file(file_path):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Determine relative path for display
    if file_path.startswith(project_dir):
        rel_path = os.path.relpath(file_path, project_dir)
    else:
        rel_path = file_path

    issues: list[str] = []

    # Run ruff format
    ret, stdout, stderr = run_command(
        ["uv", "run", "ruff", "format", file_path],
        cwd=project_dir,
    )
    if ret != 0:
        issues.append(f"ruff format failed:\n{stderr or stdout}")

    # Run ruff check with auto-fix
    ret, stdout, stderr = run_command(
        ["uv", "run", "ruff", "check", "--fix", file_path],
        cwd=project_dir,
    )
    if ret != 0:
        # Show remaining issues that couldn't be auto-fixed
        output = stdout or stderr
        if output.strip():
            issues.append(f"ruff check issues:\n{output}")

    # Run ty type check
    ret, stdout, stderr = run_command(
        ["uv", "run", "ty", "check", file_path],
        cwd=project_dir,
    )
    if ret != 0:
        output = stdout or stderr
        if output.strip():
            issues.append(f"ty check issues:\n{output}")

    # Report results via hookSpecificOutput
    if issues:
        message = f"[lint-on-save] Issues in {rel_path}:\n" + "\n".join(issues)
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": message
            }
        }, sys.stdout)
    else:
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[lint-on-save] OK: {rel_path} passed all checks"
            }
        }, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()

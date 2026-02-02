#!/usr/bin/env python3
"""
Record all hooks: Generate test fixtures for all hooks.

Generates basic test cases (happy/edge/error) for common hooks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Hook test cases configuration
HOOK_CASES = {
    "enforce-no-merge": [
        {
            "name": "happy_allow_ready",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "gh pr ready"},
            },
        },
        {
            "name": "block_gh_pr_merge",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "gh pr merge 123"},
            },
        },
        {
            "name": "block_git_merge",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "git merge main"},
            },
        },
        {
            "name": "allow_non_bash",
            "stdin": {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.txt"},
            },
        },
    ],
    "enforce-draft-pr": [
        {
            "name": "block_non_draft_pr",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh pr create --title "test"'},
            },
        },
        {
            "name": "allow_draft_pr",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh pr create --draft --title "test"'},
            },
        },
        {
            "name": "allow_non_bash",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/some/file.py"},
            },
        },
    ],
    "enforce-delegation": [
        {
            "name": "happy_delegation",
            "stdin": {
                "tool_name": "Task",
                "tool_input": {"prompt": "Do something"},
            },
        },
        {
            "name": "allow_edit_claude_files",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": ".claude/docs/DESIGN.md"},
            },
        },
        {
            "name": "warn_consecutive_work",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/main.py"},
            },
        },
    ],
    "ensure-pr-open": [
        {
            "name": "allow_read_tools",
            "stdin": {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.txt"},
            },
        },
        {
            "name": "block_write_without_pr",
            "stdin": {
                "tool_name": "Write",
                "tool_input": {"file_path": "/some/file.txt", "content": "test"},
            },
        },
    ],
    "enforce-japanese": [
        {
            "name": "block_english_pr",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh pr create --draft --title "Add feature"'},
            },
        },
        {
            "name": "allow_japanese_pr",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh pr create --draft --title "機能追加"'},
            },
        },
        {
            "name": "block_english_commit",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "Add feature"'},
            },
        },
        {
            "name": "allow_japanese_commit",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "機能追加"'},
            },
        },
    ],
}


def record_case(hook_name: str, case_name: str, stdin_data: dict) -> bool:
    """Record a single test case."""
    recorder_path = Path(__file__).parent / "record_hook.py"

    try:
        result = subprocess.run(
            [sys.executable, str(recorder_path), hook_name, case_name],
            input=str(stdin_data).replace("'", '"'),  # Convert to JSON
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"❌ Failed to record {hook_name}/{case_name}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Timeout recording {hook_name}/{case_name}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Error recording {hook_name}/{case_name}: {e}", file=sys.stderr)
        return False


def main():
    print("🎬 Recording all hook test cases...\n")

    total = 0
    success = 0

    for hook_name, cases in HOOK_CASES.items():
        print(f"\n📝 Hook: {hook_name}")
        print("─" * 60)

        for case in cases:
            total += 1
            case_name = case["name"]
            stdin_data = case["stdin"]

            if record_case(hook_name, case_name, stdin_data):
                success += 1

    print("\n" + "=" * 60)
    print(f"📊 Results: {success}/{total} cases recorded successfully")

    if success < total:
        sys.exit(1)


if __name__ == "__main__":
    main()

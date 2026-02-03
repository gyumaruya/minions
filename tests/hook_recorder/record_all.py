#!/usr/bin/env python3
"""
Record all hooks: Generate test fixtures for all hooks.

Generates basic test cases (happy/edge/error) for common hooks.
"""

from __future__ import annotations

import json
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
    "prevent-secrets-commit": [
        {
            "name": "block_aws_key",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "git add secrets.py"},
            },
        },
        {
            "name": "allow_normal_commit",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "git add main.py"},
            },
        },
        {
            "name": "allow_non_git",
            "stdin": {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.txt"},
            },
        },
    ],
    "lint-on-save": [
        {
            "name": "lint_python_file",
            "stdin": {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/main.py", "content": "x=1"},
            },
        },
        {
            "name": "skip_non_python",
            "stdin": {
                "tool_name": "Write",
                "tool_input": {"file_path": "README.md", "content": "# Test"},
            },
        },
    ],
    "agent-router": [
        {
            "name": "route_to_codex",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "どう設計すべき？エラーが出る",
            },
        },
        {
            "name": "route_to_gemini",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "調べて、このPDFを見て",
            },
        },
        {
            "name": "route_to_copilot",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "簡単な質問です",
            },
        },
    ],
    "log-cli-tools": [
        {
            "name": "log_codex_call",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "codex exec --model gpt-5.2-codex 'test'"},
            },
        },
        {
            "name": "log_gemini_call",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "gemini -p 'test'"},
            },
        },
        {
            "name": "skip_non_cli",
            "stdin": {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.txt"},
            },
        },
    ],
    "check-codex-before-write": [
        {
            "name": "suggest_codex",
            "stdin": {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "src/main.py",
                    "content": "def complex(): pass",
                },
            },
        },
        {
            "name": "skip_simple_edit",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": "README.md"},
            },
        },
    ],
    "check-codex-after-plan": [
        {
            "name": "suggest_codex_review",
            "stdin": {
                "tool_name": "Task",
                "tool_input": {"subagent_type": "Plan", "prompt": "Design system"},
            },
        },
        {
            "name": "skip_non_plan",
            "stdin": {
                "tool_name": "Task",
                "tool_input": {"subagent_type": "Explore", "prompt": "Find files"},
            },
        },
    ],
    "auto-commit-on-verify": [
        {
            "name": "suggest_commit_on_test_pass",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_output": "PASSED",
            },
        },
        {
            "name": "skip_on_test_fail",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_output": "FAILED",
            },
        },
    ],
    "post-test-analysis": [
        {
            "name": "suggest_codex_on_failure",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_output": "FAILED: AssertionError",
            },
        },
        {
            "name": "skip_on_pass",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_output": "3 passed",
            },
        },
    ],
    "post-implementation-review": [
        {
            "name": "suggest_review",
            "stdin": {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "src/feature.py",
                    "content": "class Feature: ...",
                },
            },
        },
    ],
    "suggest-gemini-research": [
        {
            "name": "suggest_gemini",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "リサーチして、調べて",
            },
        },
        {
            "name": "skip_non_research",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "コードを書いて",
            },
        },
    ],
    "auto-learn": [
        {
            "name": "learn_preference",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "PRは日本語にして",
            },
        },
        {
            "name": "learn_workflow",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "いつもテストを先に書いて",
            },
        },
    ],
    "load-memories": [
        {
            "name": "load_on_session_start",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "Hello",
            },
        },
    ],
    "hierarchy-permissions": [
        {
            "name": "grant_permissions",
            "stdin": {
                "tool_name": "Task",
                "tool_input": {"subagent_type": "general-purpose", "prompt": "Do work"},
            },
        },
    ],
    "enforce-hierarchy": [
        {
            "name": "block_upper_level_work",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/main.py"},
            },
        },
    ],
    "ensure-noreply-email": [
        {
            "name": "fix_email_in_commit",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            },
        },
    ],
    "auto-create-pr": [
        {
            "name": "create_pr_on_session_start",
            "stdin": {
                "hook_event_name": "UserPromptSubmit",
                "user_prompt": "Hello",
            },
        },
    ],
    "session-end": [
        {
            "name": "cleanup_on_end",
            "stdin": {
                "hook_event_name": "Stop",
            },
        },
    ],
    "pre-tool-recall": [
        {
            "name": "recall_memories",
            "stdin": {
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/main.py"},
            },
        },
    ],
    "post-tool-record": [
        {
            "name": "record_tool_use",
            "stdin": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_output": "PASSED",
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
            input=json.dumps(stdin_data),
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

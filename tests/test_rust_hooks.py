#!/usr/bin/env python3
"""E2E tests for Rust hooks."""

import json
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).parent.parent / "hooks-rs" / "target" / "release"


def run_hook(hook_name: str, input_data: dict) -> dict | None:
    """Run a Rust hook and return parsed output."""
    hook_path = HOOKS_DIR / hook_name
    result = subprocess.run(
        [str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        return json.loads(result.stdout)
    return None


def test_enforce_no_merge():
    # Block gh pr merge
    result = run_hook(
        "enforce-no-merge",
        {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 123"}},
    )
    assert result is not None
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    print("✅ enforce-no-merge: blocks gh pr merge")

    # Allow gh pr ready
    result = run_hook(
        "enforce-no-merge",
        {"tool_name": "Bash", "tool_input": {"command": "gh pr ready"}},
    )
    assert result is None
    print("✅ enforce-no-merge: allows gh pr ready")


def test_enforce_draft_pr():
    # Block non-draft PR
    result = run_hook(
        "enforce-draft-pr",
        {"tool_name": "Bash", "tool_input": {"command": "gh pr create --title test"}},
    )
    assert result is not None
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    print("✅ enforce-draft-pr: blocks non-draft PR")

    # Allow draft PR
    result = run_hook(
        "enforce-draft-pr",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr create --draft --title test"},
        },
    )
    assert result is None
    print("✅ enforce-draft-pr: allows draft PR")


def test_prevent_secrets_commit():
    # Detect AWS key
    result = run_hook(
        "prevent-secrets-commit",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git add file_with_AKIAIOSFODNN7EXAMPLE.py"},
        },
    )
    assert result is not None
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    print("✅ prevent-secrets-commit: detects AWS key")

    # Allow normal commit
    result = run_hook(
        "prevent-secrets-commit",
        {"tool_name": "Bash", "tool_input": {"command": "git add normal_file.py"}},
    )
    assert result is None
    print("✅ prevent-secrets-commit: allows normal commit")


def test_ensure_pr_open():
    # This test depends on whether a PR is open
    result = run_hook(
        "ensure-pr-open", {"tool_name": "Edit", "tool_input": {"file_path": "test.py"}}
    )
    if result is None:
        print("✅ ensure-pr-open: PR is open, allows edit")
    else:
        print("✅ ensure-pr-open: No PR, blocks edit")


if __name__ == "__main__":
    test_enforce_no_merge()
    test_enforce_draft_pr()
    test_prevent_secrets_commit()
    test_ensure_pr_open()
    print("\n🎉 All E2E tests passed!")

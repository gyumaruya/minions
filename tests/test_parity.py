#!/usr/bin/env python3
"""
Parity tests: Compare Python and Rust hook behavior.

Ensures Rust hooks produce equivalent output to Python hooks.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYTHON_HOOKS = REPO_ROOT / ".claude" / "hooks"
RUST_HOOKS = REPO_ROOT / "hooks-rs" / "target" / "release"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hooks"


def run_python_hook(hook_name: str, input_data: dict) -> tuple[str, int]:
    """Run Python hook and return (stdout, exit_code)."""
    hook_path = PYTHON_HOOKS / f"{hook_name}.py"
    if not hook_path.exists():
        return "", -1

    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.returncode


def run_rust_hook(hook_name: str, input_data: dict) -> tuple[str, int]:
    """Run Rust hook and return (stdout, exit_code)."""
    hook_path = RUST_HOOKS / hook_name
    if not hook_path.exists():
        return "", -1

    result = subprocess.run(
        [str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.returncode


def normalize_output(output: str) -> dict | None:
    """Normalize hook output for comparison."""
    if not output.strip():
        return None

    try:
        data = json.loads(output)
        # Normalize: extract key decision fields
        hook_output = data.get("hookSpecificOutput", {})
        return {
            "decision": hook_output.get("permissionDecision"),
            "has_context": bool(
                hook_output.get("additionalContext")
                or hook_output.get("permissionDecisionReason")
            ),
            "has_error": bool(hook_output.get("blockingError")),
        }
    except json.JSONDecodeError:
        return {"raw": output}


def compare_hooks(hook_name: str, input_data: dict) -> bool:
    """Compare Python and Rust hook behavior."""
    py_out, py_exit = run_python_hook(hook_name, input_data)
    rs_out, rs_exit = run_rust_hook(hook_name, input_data)

    py_norm = normalize_output(py_out)
    rs_norm = normalize_output(rs_out)

    # Compare normalized outputs
    if py_norm == rs_norm:
        return True

    # Both deny or both allow is equivalent
    if py_norm and rs_norm:
        if py_norm.get("decision") == rs_norm.get("decision"):
            return True

    # Both silent pass is equivalent
    if py_norm is None and rs_norm is None:
        return True

    print(f"  Mismatch for {hook_name}:")
    print(f"    Python: {py_norm}")
    print(f"    Rust:   {rs_norm}")
    return False


def test_enforce_no_merge_parity():
    """Test enforce-no-merge parity."""
    print("\n🔄 Testing enforce-no-merge parity...")

    cases = [
        (
            "block_merge",
            {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 123"}},
        ),
        (
            "allow_ready",
            {"tool_name": "Bash", "tool_input": {"command": "gh pr ready"}},
        ),
        ("allow_view", {"tool_name": "Bash", "tool_input": {"command": "gh pr view"}}),
        ("non_bash", {"tool_name": "Read", "tool_input": {"file_path": "test.txt"}}),
    ]

    passed = 0
    for name, input_data in cases:
        if compare_hooks("enforce-no-merge", input_data):
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")

    return passed == len(cases)


def test_enforce_draft_pr_parity():
    """Test enforce-draft-pr parity."""
    print("\n🔄 Testing enforce-draft-pr parity...")

    cases = [
        (
            "block_non_draft",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "gh pr create --title test"},
            },
        ),
        (
            "allow_draft",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "gh pr create --draft --title test"},
            },
        ),
        ("non_bash", {"tool_name": "Edit", "tool_input": {"file_path": "test.py"}}),
    ]

    passed = 0
    for name, input_data in cases:
        if compare_hooks("enforce-draft-pr", input_data):
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")

    return passed == len(cases)


def test_prevent_secrets_commit_parity():
    """Test prevent-secrets-commit parity."""
    print("\n🔄 Testing prevent-secrets-commit parity...")

    cases = [
        (
            "detect_aws",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git add AKIAIOSFODNN7EXAMPLE"},
            },
        ),
        (
            "allow_normal",
            {"tool_name": "Bash", "tool_input": {"command": "git add main.py"}},
        ),
        ("non_git", {"tool_name": "Read", "tool_input": {"file_path": "test.txt"}}),
    ]

    passed = 0
    for name, input_data in cases:
        if compare_hooks("prevent-secrets-commit", input_data):
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")

    return passed == len(cases)


def main():
    print("=" * 60)
    print("Parity Tests: Python vs Rust Hooks")
    print("=" * 60)

    results = []
    results.append(("enforce-no-merge", test_enforce_no_merge_parity()))
    results.append(("enforce-draft-pr", test_enforce_draft_pr_parity()))
    results.append(("prevent-secrets-commit", test_prevent_secrets_commit_parity()))

    print("\n" + "=" * 60)
    print("Summary:")
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All parity tests passed!")
    else:
        print("\n❌ Some parity tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

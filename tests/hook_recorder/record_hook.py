#!/usr/bin/env python3
"""
Hook Recorder: Record hook execution for testing.

Usage:
    echo '{"tool_name": "Bash", "tool_input": {...}}' | python record_hook.py <hook_name> <case_name>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def normalize_json(data: Any) -> Any:
    """Normalize JSON for deterministic comparison.

    - Sort keys
    - Remove volatile fields (timestamp, session_id, ppid, etc.)
    - Normalize whitespace
    """
    if isinstance(data, dict):
        # Remove volatile fields
        volatile_keys = {
            "timestamp",
            "session_id",
            "ppid",
            "pid",
            "datetime",
            "execution_time",
            "duration",
        }
        normalized = {
            k: normalize_json(v) for k, v in data.items() if k not in volatile_keys
        }
        # Sort keys for deterministic ordering
        return dict(sorted(normalized.items()))
    elif isinstance(data, list):
        return [normalize_json(item) for item in data]
    else:
        return data


def record_hook(hook_name: str, case_name: str, stdin_data: dict[str, Any]) -> None:
    """Record hook execution with input/output."""
    # Find hook script
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / ".claude" / "hooks" / f"{hook_name}.py"

    if not hook_path.exists():
        print(f"❌ Hook not found: {hook_path}", file=sys.stderr)
        sys.exit(1)

    # Create case directory
    fixtures_dir = (
        repo_root / "tests" / "fixtures" / "hooks" / hook_name / "cases" / case_name
    )
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Save stdin
    stdin_file = fixtures_dir / "stdin.json"
    with stdin_file.open("w") as f:
        json.dump(stdin_data, f, indent=2, sort_keys=True)

    # Execute hook
    try:
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(stdin_data),
            capture_output=True,
            text=True,
            timeout=10,
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

    except subprocess.TimeoutExpired:
        print(f"❌ Hook timeout: {hook_name}", file=sys.stderr)
        sys.exit(1)

    # Parse and normalize stdout JSON (if valid)
    expected_output = None
    if stdout.strip():
        try:
            stdout_json = json.loads(stdout)
            expected_output = normalize_json(stdout_json)
        except json.JSONDecodeError:
            # Not JSON, keep as is
            expected_output = stdout

    # Save expected output
    if expected_output:
        expected_file = fixtures_dir / "expected.json"
        with expected_file.open("w") as f:
            if isinstance(expected_output, dict):
                json.dump(expected_output, f, indent=2, sort_keys=True)
            else:
                f.write(str(expected_output))

    # Save metadata
    meta = {
        "exit_code": exit_code,
        "stderr": stderr if stderr else None,
        "description": f"{hook_name} - {case_name} case",
    }
    meta_file = fixtures_dir / "meta.yaml"
    with meta_file.open("w") as f:
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ Recorded: {hook_name}/{case_name}")
    print(f"   stdin:    {stdin_file}")
    print(f"   expected: {expected_file if expected_output else '(empty)'}")
    print(f"   meta:     {meta_file}")
    print(f"   exit:     {exit_code}")


def main():
    parser = argparse.ArgumentParser(description="Record hook execution for testing")
    parser.add_argument("hook_name", help="Hook name (without .py extension)")
    parser.add_argument("case_name", help="Test case name (e.g., happy, edge, error)")

    args = parser.parse_args()

    # Read stdin JSON
    try:
        stdin_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)

    record_hook(args.hook_name, args.case_name, stdin_data)


if __name__ == "__main__":
    main()

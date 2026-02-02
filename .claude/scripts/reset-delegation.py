#!/usr/bin/env python3
"""
Reset delegation counter for conductor.

Usage:
    python .claude/scripts/reset-delegation.py [--reason "理由"]

This is an explicit reset command for emergency situations.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    # Parse reason from command line arguments
    args = sys.argv[1:]
    reason = "手動リセット"
    if args:
        # Join all args as reason
        if args[0] == "--reason" and len(args) > 1:
            reason = " ".join(args[1:])
        else:
            reason = " ".join(args)

    session_id = os.environ.get("CLAUDE_SESSION_ID", str(os.getppid()))
    state_path = Path("/tmp") / f"claude-delegation-{session_id}-conductor.json"

    # Reset state
    state = {
        "last_delegation_ts": 0,
        "non_delegate_count": 0,
        "last_warning_at": 0,
        "window_start_ts": 0,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    # Log the reset
    log_path = Path(".claude/logs/delegation-resets.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "reason": reason,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"✅ 委譲カウンターをリセットしました。理由: {reason}")


if __name__ == "__main__":
    main()

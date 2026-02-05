#!/usr/bin/env bash
# Verification trigger on agent completion
# Triggered by Stop/SubagentStop hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Read input JSON from stdin
input_json="$(cat)"

# Check if stop_hook_active to prevent recursion
stop_active="$(echo "$input_json" | jq -r '.stop_hook_active // false')"
if [[ "$stop_active" == "true" ]]; then
    exit 0
fi

# Get transcript path
transcript_path="$(echo "$input_json" | jq -r '.transcript_path // empty')"
if [[ -z "$transcript_path" || ! -f "$transcript_path" ]]; then
    exit 0
fi

# Extract last assistant message from transcript
last_assistant="$(python3 - "$transcript_path" <<'PY'
import json
import sys

path = sys.argv[1]
last = ""

try:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            # Get role (various formats)
            role = obj.get("role") or obj.get("message", {}).get("role")
            if role != "assistant":
                continue

            # Get content (various formats)
            content = obj.get("content") or obj.get("message", {}).get("content")
            if isinstance(content, list):
                # Extract text from list of content blocks
                content = " ".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and "text" in part
                )

            if content:
                last = str(content)
except Exception:
    pass

print(last.strip() if isinstance(last, str) else "")
PY
)"

if [[ -z "$last_assistant" ]]; then
    exit 0
fi

# Check for completion intent using Claude Haiku
# Create prompt for AI judgment
prompt="以下のメッセージを分析して、作業完了を意図しているかどうかを判定してください。

【判定基準】
- 作業・タスク・実装が完了したことを明示的に述べている
- 「できました」「完了」「終わりました」「仕上がりました」などの完了表現
- 英語の場合: \"done\", \"finished\", \"completed\", \"ready\" など

【メッセージ】
$last_assistant

【出力形式】
完了を意図している場合のみ「YES」を出力。それ以外は「NO」を出力。
理由は不要。YESまたはNOのみ。"

# Use AI to determine if the message indicates task completion
completion_check="$(claude -p "$prompt" --model haiku --output-format text 2>/dev/null)"

completion_check_upper="$(echo "$completion_check" | tr '[:lower:]' '[:upper:]' | xargs)"

if [[ "$completion_check_upper" == "YES" ]]; then
    # Prevent duplicate runs with lock file
    lock_file="/tmp/claude-verify-lock-$(echo "$transcript_path" | md5)"

    if [[ -f "$lock_file" ]]; then
        # Already verified this completion
        exit 0
    fi

    # Create lock file
    touch "$lock_file"

    # Run verification
    "$SCRIPT_DIR/verify.sh"

    # Clean up lock file after some time (background)
    (sleep 300 && rm -f "$lock_file") &
fi

exit 0

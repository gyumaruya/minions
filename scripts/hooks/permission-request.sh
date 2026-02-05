#!/usr/bin/env bash
# Permission Request Hook: Evaluates risky operations via LLM judgment
# Hook Type: PermissionRequest
# Response Format: {"decision": "allow"} | {"decision": "deny", "message": "..."} | {"decision": "ask_user", "message": "..."}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common libraries
source "$SCRIPT_DIR/lib/llm_judge.sh"
source "$SCRIPT_DIR/lib/recursion_guard.sh"

# Read input from stdin
input_json="$(cat)"

# Prevent recursion
if ! acquire_lock "permission-request" 30; then
    # Already processing, allow to prevent blocking
    echo '{"decision": "allow"}'
    exit 0
fi

# Cleanup on exit
trap 'release_lock "permission-request"' EXIT

# Extract tool name and input
tool_name="$(echo "$input_json" | jq -r '.tool_name // empty')"
tool_input="$(echo "$input_json" | jq -r '.tool_input // empty')"

if [[ -z "$tool_name" ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Check for secret file access FIRST (before whitelist)
if [[ "$tool_name" == "Read" || "$tool_name" == "Edit" || "$tool_name" == "Write" ]]; then
    file_path="$(echo "$tool_input" | jq -r '.file_path // .path // empty')"

    # Check for .env files (exact match or in path)
    if [[ "$file_path" == ".env" || "$file_path" == *"/.env" || "$file_path" == *.env.* || "$file_path" == *"/.env."* ]]; then
        echo '{"decision": "deny", "message": "Access to .env files is prohibited"}'
        exit 0
    fi

    # Check for other secret files
    case "$file_path" in
        *credentials*|*secret*|*.pem|*.key)
            echo '{"decision": "deny", "message": "Access to credential/secret files is prohibited"}'
            exit 0
            ;;
    esac
fi

# Fast-path: Whitelist common safe operations
case "$tool_name" in
    "Read"|"Glob"|"Grep"|"LS")
        # Read-only operations are generally safe
        echo '{"decision": "allow"}'
        exit 0
        ;;
esac

# Check for Bash command whitelist
if [[ "$tool_name" == "Bash" ]]; then
    command_str="$(echo "$tool_input" | jq -r '.command // empty')"

    # Whitelist safe commands
    case "$command_str" in
        "git status"*|"git diff"*|"git log"*|"git branch"*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "pytest"*|"ruff check"*|"ruff format"*|"uv run"*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "ls"*|"pwd"|"cat"*|"head"*|"tail"*|"wc"*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "echo"*|"date"|"which"*|"type"*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
    esac

    # Blacklist dangerous commands
    case "$command_str" in
        "rm -rf /"*|"rm -rf /*"|"sudo rm -rf"*)
            echo '{"decision": "deny", "message": "Dangerous operation: System-wide deletion is prohibited"}'
            exit 0
            ;;
        "gh pr merge"*|"git merge"*)
            echo '{"decision": "deny", "message": "Merge operations by agents are prohibited. Please merge manually via GitHub UI or CLI"}'
            exit 0
            ;;
        "git push --force"*"main"*|"git push --force"*"master"*)
            echo '{"decision": "deny", "message": "Force push to main/master is prohibited"}'
            exit 0
            ;;
    esac
fi

# For other operations, use LLM judgment
agent_def_path="$PROJECT_ROOT/.claude/agents/permission-judge.md"

if [[ ! -f "$agent_def_path" ]]; then
    # No agent definition, default to allow
    echo '{"decision": "allow"}'
    exit 0
fi

# Prepare input for LLM
llm_input="$(cat <<EOF
{
  "tool": "$tool_name",
  "input": $tool_input
}
EOF
)"

# Call LLM judge
response="$(llm_judge "$agent_def_path" "$llm_input" "Evaluate this operation and provide judgment")"

# Validate response format
decision="$(echo "$response" | jq -r '.decision // empty')"

case "$decision" in
    "allow")
        echo '{"decision": "allow"}'
        ;;
    "deny")
        message="$(echo "$response" | jq -r '.message // "Operation denied"')"
        echo "{\"decision\": \"deny\", \"message\": \"$message\"}"
        ;;
    "ask_user")
        message="$(echo "$response" | jq -r '.message // "User confirmation required"')"
        echo "{\"decision\": \"ask_user\", \"message\": \"$message\"}"
        ;;
    *)
        # Invalid response, default to allow
        echo '{"decision": "allow"}'
        ;;
esac

exit 0

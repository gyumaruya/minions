#!/usr/bin/env bash
# Permission Request Hook: Evaluates risky operations via LLM judgment
# Hook Type: PermissionRequest
# Response Format: {"decision": "allow"} | {"decision": "deny", "message": "..."} | {"decision": "ask_user", "message": "..."}
#
# Security: deny-by-default design. Failed parsing/LLM calls result in deny or ask_user.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check for required commands
if ! command -v jq &> /dev/null; then
    echo '{"decision": "ask_user", "message": "jq is not installed. Cannot evaluate safely."}'
    exit 0
fi

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

    # SECURITY: Check for shell metacharacters that could be used for command injection
    # Deny any command containing: ; && || | > < ` $( { }
    if [[ "$command_str" =~ [;\&\|><\`\$\(\)\{\}] ]]; then
        # Allow safe patterns with pipes/redirects
        case "$command_str" in
            "git log"*"|"*"head"*|"git diff"*"|"*"head"*)
                # Safe: git log | head patterns
                ;;
            *"2>/dev/null"*|*">/dev/null"*)
                # Safe: stderr/stdout suppression
                ;;
            *)
                echo '{"decision": "ask_user", "message": "Command contains shell metacharacters. Please review: '"$command_str"'"}'
                exit 0
                ;;
        esac
    fi

    # Whitelist safe commands (exact match or safe prefix patterns)
    # Using regex for stricter matching
    case "$command_str" in
        "git status"|"git status "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git diff"|"git diff "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git log"|"git log "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git branch"|"git branch "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git add"|"git add "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git commit"|"git commit "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "git push"|"git push "*)
            # Check for force push to main/master
            if [[ "$command_str" =~ --force.*main|--force.*master|-f.*main|-f.*master ]]; then
                echo '{"decision": "deny", "message": "Force push to main/master is prohibited"}'
                exit 0
            fi
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "pytest"|"pytest "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "ruff check"|"ruff check "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "ruff format"|"ruff format "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "uv run"|"uv run "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "uv sync"|"uv add"|"uv add "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "ls"|"ls "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "pwd")
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "date"|"which"|"which "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "type"|"type "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "copilot"|"copilot "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "codex"|"codex "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "gemini"|"gemini "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "gh pr"|"gh pr "*)
            # Check for prohibited operations (combine/join PRs)
            if [[ "$command_str" =~ gh\ pr\ (combine|join) ]]; then
                echo '{"decision": "deny", "message": "PR combine operations by agents are prohibited"}'
                exit 0
            fi
            echo '{"decision": "allow"}'
            exit 0
            ;;
        "gh issue"|"gh issue "*)
            echo '{"decision": "allow"}'
            exit 0
            ;;
    esac

    # Blacklist dangerous commands
    case "$command_str" in
        "rm -rf /"|"rm -rf /*"|"sudo rm"*)
            echo '{"decision": "deny", "message": "Dangerous operation: System-wide deletion is prohibited"}'
            exit 0
            ;;
        *"curl"*"|"*"bash"*|*"wget"*"|"*"sh"*)
            echo '{"decision": "deny", "message": "Piping remote scripts to shell is prohibited"}'
            exit 0
            ;;
        "sudo "*)
            echo '{"decision": "ask_user", "message": "sudo commands require user approval: '"$command_str"'"}'
            exit 0
            ;;
    esac
fi

# For other operations, use LLM judgment (deny-by-default)
agent_def_path="$PROJECT_ROOT/.claude/agents/permission-judge.md"

if [[ ! -f "$agent_def_path" ]]; then
    # No agent definition, ask user (deny-by-default)
    echo '{"decision": "ask_user", "message": "Unknown operation requires user approval: '"$tool_name"'"}'
    exit 0
fi

# Prepare input for LLM with proper JSON escaping
llm_input="$(jq -n \
    --arg tool "$tool_name" \
    --argjson input "$tool_input" \
    '{tool: $tool, input: $input}' 2>/dev/null)"

if [[ -z "$llm_input" || "$llm_input" == "null" ]]; then
    # JSON construction failed, ask user
    echo '{"decision": "ask_user", "message": "Failed to parse tool input. Please review manually."}'
    exit 0
fi

# Call LLM judge
response="$(llm_judge "$agent_def_path" "$llm_input" "Evaluate this operation and provide judgment")"

# Validate response format strictly with jq -e
if ! echo "$response" | jq -e '.decision' &>/dev/null; then
    # Invalid JSON response, ask user (deny-by-default)
    echo '{"decision": "ask_user", "message": "LLM judgment failed. Please review manually."}'
    exit 0
fi

decision="$(echo "$response" | jq -r '.decision // empty')"

case "$decision" in
    "allow")
        echo '{"decision": "allow"}'
        ;;
    "deny")
        message="$(echo "$response" | jq -r '.message // "Operation denied"')"
        # Escape message for JSON output
        escaped_message="$(echo "$message" | jq -Rs '.[:-1]')"
        echo "{\"decision\": \"deny\", \"message\": $escaped_message}"
        ;;
    "ask_user")
        message="$(echo "$response" | jq -r '.message // "User confirmation required"')"
        escaped_message="$(echo "$message" | jq -Rs '.[:-1]')"
        echo "{\"decision\": \"ask_user\", \"message\": $escaped_message}"
        ;;
    *)
        # Invalid decision, ask user (deny-by-default)
        echo '{"decision": "ask_user", "message": "Unexpected LLM response. Please review manually."}'
        ;;
esac

exit 0

#!/usr/bin/env bash
# Notification Hook: Provides guidance and answers questions via LLM
# Hook Type: Notification
# Response Format: {"message": "..."} (optional)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common libraries
source "$SCRIPT_DIR/lib/llm_judge.sh"
source "$SCRIPT_DIR/lib/recursion_guard.sh"

# Read input from stdin
input_json="$(cat)"

# Prevent recursion
if ! acquire_lock "notification" 30; then
    # Already processing, skip
    exit 0
fi

# Cleanup on exit
trap 'release_lock "notification"' EXIT

# Extract notification type and content
notification_type="$(echo "$input_json" | jq -r '.type // empty')"
content="$(echo "$input_json" | jq -r '.content // .message // empty')"

if [[ -z "$notification_type" ]]; then
    # No notification type, nothing to do
    exit 0
fi

# Fast-path: Skip certain notification types
case "$notification_type" in
    "debug"|"trace"|"verbose")
        # Skip debug notifications
        exit 0
        ;;
esac

# Load agent definition
agent_def_path="$PROJECT_ROOT/.claude/agents/notification-agent.md"

if [[ ! -f "$agent_def_path" ]]; then
    # No agent definition, skip
    exit 0
fi

# Prepare input for LLM
llm_input="$(cat <<EOF
{
  "event": "$notification_type",
  "content": $(echo "$content" | jq -Rs '.')
}
EOF
)"

# Determine if LLM consultation is needed
needs_llm=false

case "$notification_type" in
    "task_started"|"task_completed")
        # Simple progress notifications, use template
        ;;
    "error"|"warning"|"incomplete_tasks")
        # May need LLM guidance
        needs_llm=true
        ;;
    "question"|"help_needed")
        # Definitely needs LLM
        needs_llm=true
        ;;
    *)
        # Unknown type, let LLM handle
        needs_llm=true
        ;;
esac

if [[ "$needs_llm" == "true" ]]; then
    # Call LLM for guidance
    response="$(llm_judge "$agent_def_path" "$llm_input" "Provide helpful notification or guidance")"

    # Extract message
    message="$(echo "$response" | jq -r '.message // empty')"

    if [[ -n "$message" ]]; then
        echo "{\"message\": $(echo "$message" | jq -Rs '.')}"
    fi
else
    # Use simple templates for common notifications
    case "$notification_type" in
        "task_started")
            task_name="$(echo "$content" | jq -r '.task // "Unknown task"' 2>/dev/null || echo "$content")"
            echo "{\"message\": \"Task started: $task_name\"}"
            ;;
        "task_completed")
            task_name="$(echo "$content" | jq -r '.task // "Unknown task"' 2>/dev/null || echo "$content")"
            echo "{\"message\": \"Task completed: $task_name\"}"
            ;;
        *)
            # No message needed
            ;;
    esac
fi

exit 0

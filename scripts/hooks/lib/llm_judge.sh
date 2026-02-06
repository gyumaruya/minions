#!/usr/bin/env bash
# LLM Judge: Common function for Opus 4.5 judgment via Copilot CLI
# Usage: source this file, then call llm_judge "agent_def_path" "input_json"

set -uo pipefail

# Call Opus 4.5 via Copilot CLI for judgment
# This prevents infinite recursion because Copilot CLI doesn't trigger Claude hooks
#
# Args:
#   $1: Path to agent definition file (.md)
#   $2: Input JSON to pass to the agent
#   $3: (Optional) Task description
#
# Returns:
#   JSON response from the agent (stdout)
#   Exit code 0 on success, 1 on failure
llm_judge() {
    local agent_def_path="$1"
    local input_json="$2"
    local task_desc="${3:-Evaluate the input and provide judgment}"

    if [[ ! -f "$agent_def_path" ]]; then
        echo '{"error": "Agent definition not found"}'
        return 1
    fi

    local agent_def
    agent_def="$(cat "$agent_def_path")"

    # Build prompt for Opus 4.5 via Copilot CLI
    local prompt
    prompt="$(cat <<EOF
サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

$agent_def

## Input

\`\`\`json
$input_json
\`\`\`

## Task

$task_desc

## Output Format

JSONのみを出力してください。説明やコードブロックのマークアップは不要です。
EOF
)"

    # Call Copilot CLI (doesn't trigger Claude hooks internally)
    local raw_response
    raw_response="$(copilot -p "$prompt" --model claude-sonnet-4 --allow-all --silent 2>/dev/null)" || {
        echo '{"error": "LLM call failed", "decision": "ask_user"}'
        return 1
    }

    # Clean up response: extract JSON from possible markdown code blocks
    local response=""

    # Try to extract JSON using jq (most reliable)
    if command -v jq &>/dev/null; then
        # First, try to parse the entire response as JSON
        if echo "$raw_response" | jq -e '.' &>/dev/null; then
            response="$raw_response"
        else
            # Try to extract JSON from markdown code blocks or inline
            # Look for ```json ... ``` or { ... }
            local extracted
            extracted="$(echo "$raw_response" | sed -n 's/.*```json\s*//p' | sed -n 's/\s*```.*//p' | head -1)"
            if [[ -n "$extracted" ]] && echo "$extracted" | jq -e '.' &>/dev/null; then
                response="$extracted"
            else
                # Try to find any valid JSON object
                extracted="$(echo "$raw_response" | grep -oE '\{[^{}]*\}' | head -1)"
                if [[ -n "$extracted" ]] && echo "$extracted" | jq -e '.' &>/dev/null; then
                    response="$extracted"
                fi
            fi
        fi
    fi

    # If we couldn't extract valid JSON, return error
    if [[ -z "$response" ]]; then
        echo '{"error": "No valid JSON in response", "decision": "ask_user"}'
        return 1
    fi

    echo "$response"
}

# Simple yes/no judgment using LLM
# Returns "YES" or "NO"
llm_judge_yesno() {
    local agent_def_path="$1"
    local input_json="$2"
    local question="${3:-Is this acceptable?}"

    local prompt
    prompt="$(cat <<EOF
サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

## Agent Definition

$(cat "$agent_def_path" 2>/dev/null || echo "No agent definition")

## Input

$input_json

## Question

$question

## Output

YESまたはNOのみを出力してください。理由は不要です。
EOF
)"

    local response
    response="$(copilot -p "$prompt" --model claude-sonnet-4 --allow-all --silent 2>/dev/null || echo "NO")"

    # Normalize response
    response="$(echo "$response" | tr '[:lower:]' '[:upper:]' | xargs | head -c 3)"

    if [[ "$response" == "YES" ]]; then
        echo "YES"
    else
        echo "NO"
    fi
}

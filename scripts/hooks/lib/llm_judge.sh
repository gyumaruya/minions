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
    local response
    response="$(copilot -p "$prompt" --model claude-sonnet-4 --allow-all --silent 2>/dev/null || echo '{"error": "LLM call failed"}')"

    # Clean up response: extract JSON from possible markdown code blocks
    response="$(echo "$response" | sed -n '/^{/,/^}/p' | head -1)"

    # If response doesn't start with {, try to extract JSON
    if [[ ! "$response" =~ ^\{ ]]; then
        # Try to find JSON in the response
        response="$(echo "$response" | grep -o '{[^}]*}' | head -1 || echo '{"error": "No JSON in response"}')"
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

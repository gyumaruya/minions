#!/usr/bin/env bash
# Verifier: Functions to verify completion criteria
# Used by stop-judge and other verification hooks

set -uo pipefail

# Run all verification checks and return JSON result
# Returns JSON with check results
run_verification_checks() {
    local project_root="${1:-.}"
    cd "$project_root" || return 1

    local lint_result="pass"
    local format_result="pass"
    local tests_result="pass"
    local git_status="clean"
    local codex_reviewed="false"
    local remaining_todos=0

    # Lint check
    if command -v uv &> /dev/null; then
        if ! uv run ruff check . &> /dev/null; then
            lint_result="fail"
        fi
    fi

    # Format check
    if command -v uv &> /dev/null; then
        if ! uv run ruff format --check . &> /dev/null; then
            format_result="fail"
        fi
    fi

    # Test check (only if tests directory exists)
    if [[ -d "tests" ]] && command -v uv &> /dev/null; then
        if ! uv run pytest tests/ -q &> /dev/null; then
            tests_result="fail"
        fi
    fi

    # Git status check
    if command -v git &> /dev/null; then
        local status
        status="$(git status --porcelain 2>/dev/null)"
        if [[ -n "$status" ]]; then
            git_status="dirty"
        fi
    fi

    # Check for Codex review in logs
    local log_file=".claude/logs/cli-tools.jsonl"
    if [[ -f "$log_file" ]]; then
        # Check for recent Codex review (within last hour)
        local one_hour_ago
        one_hour_ago="$(date -v-1H +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || echo "")"

        if [[ -n "$one_hour_ago" ]]; then
            if grep -q '"tool":"codex"' "$log_file" 2>/dev/null && \
               grep -q "review\|Review\|REVIEW" "$log_file" 2>/dev/null; then
                codex_reviewed="true"
            fi
        fi
    fi

    # Count remaining TODOs
    if command -v grep &> /dev/null; then
        remaining_todos="$(grep -rn "TODO\|FIXME\|XXX" --include="*.py" --include="*.rs" --include="*.ts" --include="*.js" . 2>/dev/null | wc -l | xargs || echo "0")"
    fi

    # Output JSON
    cat <<EOF
{
  "lint": "$lint_result",
  "format": "$format_result",
  "tests": "$tests_result",
  "git_status": "$git_status",
  "codex_reviewed": $codex_reviewed,
  "remaining_todos": $remaining_todos
}
EOF
}

# Check if all verification criteria pass
# Returns 0 if all pass, 1 if any fail
all_checks_pass() {
    local checks_json="$1"

    local lint format tests git_status codex_reviewed todos

    lint="$(echo "$checks_json" | jq -r '.lint')"
    format="$(echo "$checks_json" | jq -r '.format')"
    tests="$(echo "$checks_json" | jq -r '.tests')"
    git_status="$(echo "$checks_json" | jq -r '.git_status')"
    codex_reviewed="$(echo "$checks_json" | jq -r '.codex_reviewed')"
    todos="$(echo "$checks_json" | jq -r '.remaining_todos')"

    if [[ "$lint" == "pass" ]] && \
       [[ "$format" == "pass" ]] && \
       [[ "$tests" == "pass" ]] && \
       [[ "$git_status" == "clean" ]] && \
       [[ "$codex_reviewed" == "true" ]] && \
       [[ "$todos" == "0" ]]; then
        return 0
    fi

    return 1
}

# Generate failure message from checks
# Returns human-readable failure message
generate_failure_message() {
    local checks_json="$1"
    local message=""

    local lint format tests git_status codex_reviewed todos

    lint="$(echo "$checks_json" | jq -r '.lint')"
    format="$(echo "$checks_json" | jq -r '.format')"
    tests="$(echo "$checks_json" | jq -r '.tests')"
    git_status="$(echo "$checks_json" | jq -r '.git_status')"
    codex_reviewed="$(echo "$checks_json" | jq -r '.codex_reviewed')"
    todos="$(echo "$checks_json" | jq -r '.remaining_todos')"

    message="以下を完了してください:\n\n"

    local count=1

    if [[ "$lint" != "pass" ]]; then
        message+="${count}. Lint エラーを修正: ruff check --fix .\n"
        count=$((count + 1))
    fi

    if [[ "$format" != "pass" ]]; then
        message+="${count}. フォーマットを修正: ruff format .\n"
        count=$((count + 1))
    fi

    if [[ "$tests" != "pass" ]]; then
        message+="${count}. テストを修正: pytest で失敗しているテストを確認\n"
        count=$((count + 1))
    fi

    if [[ "$git_status" != "clean" ]]; then
        message+="${count}. Git の未コミット変更を整理\n"
        count=$((count + 1))
    fi

    if [[ "$codex_reviewed" != "true" ]]; then
        message+="${count}. Codex レビューを受ける\n"
        count=$((count + 1))
    fi

    if [[ "$todos" != "0" ]]; then
        message+="${count}. TODO/FIXME を解決 (${todos}件残っています)\n"
        count=$((count + 1))
    fi

    echo -e "$message"
}

# Quick lint check only
check_lint() {
    local project_root="${1:-.}"
    cd "$project_root" || return 1

    if command -v uv &> /dev/null; then
        if uv run ruff check . &> /dev/null; then
            echo "pass"
            return 0
        fi
    fi

    echo "fail"
    return 1
}

# Quick test check only
check_tests() {
    local project_root="${1:-.}"
    cd "$project_root" || return 1

    if [[ -d "tests" ]] && command -v uv &> /dev/null; then
        if uv run pytest tests/ -q &> /dev/null; then
            echo "pass"
            return 0
        fi
        echo "fail"
        return 1
    fi

    # No tests directory, consider pass
    echo "pass"
    return 0
}

#!/usr/bin/env bash
# Agent Call Dashboard - Shows call history for each agent
set -uo pipefail

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
GRAY='\033[0;90m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
REFRESH_INTERVAL=${REFRESH_INTERVAL:-5}
# Use project-relative path or CLAUDE_PROJECT_DIR if set
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
LOG_DIR="${PROJECT_DIR}/.claude/logs"
CALL_LOG="${LOG_DIR}/agent-calls.log"

mkdir -p "$LOG_DIR" 2>/dev/null || true
touch "$CALL_LOG" 2>/dev/null || true

# Get call count for agent
get_count() {
    if [[ -f "$CALL_LOG" ]]; then
        grep -c "^$1:" "$CALL_LOG" 2>/dev/null || true
    else
        echo 0
    fi
}

# Get last call time for agent
get_last_call() {
    local last
    last=$(grep "^$1:" "$CALL_LOG" 2>/dev/null | tail -1 | cut -d: -f2-)
    if [[ -n "$last" ]]; then
        echo "$last"
    else
        echo "-"
    fi
}

# Get calls in last N minutes
get_recent() {
    local agent=$1
    local mins=${2:-60}
    local threshold
    threshold=$(date -v-${mins}M '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d "$mins minutes ago" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "")

    if [[ -z "$threshold" ]]; then
        echo "-"
        return
    fi

    local count=0
    while IFS=: read -r name timestamp; do
        if [[ "$name" == "$agent" && "$timestamp" > "$threshold" ]]; then
            ((count++))
        fi
    done < "$CALL_LOG"
    echo "$count"
}

# Main display
main() {
    while true; do
        clear

        local total
        total=$(wc -l < "$CALL_LOG" 2>/dev/null | tr -d ' ')
        total=${total:-0}

        echo ""
        printf "${CYAN}${BOLD}  Agent Call Dashboard${NC}                        ${GRAY}Total: ${total} calls${NC}\n"
        echo ""

        # Header
        printf "${BOLD}  %-12s  %8s  %8s  %-20s${NC}\n" "AGENT" "TOTAL" "LAST 1H" "LAST CALL"
        printf "${GRAY}  %-12s  %8s  %8s  %-20s${NC}\n" "────────────" "────────" "────────" "────────────────────"

        # Data rows
        for agent in claude codex gemini copilot; do
            local count last_call recent
            count=$(get_count "$agent")
            recent=$(get_recent "$agent" 60)
            last_call=$(get_last_call "$agent")

            # Color based on activity
            local color=$NC
            if [[ "$count" -gt 0 ]]; then
                color=$GREEN
            fi

            printf "${color}  %-12s  %8s  %8s  %-20s${NC}\n" "$agent" "$count" "$recent" "$last_call"
        done

        echo ""
        printf "${GRAY}  Updated: $(date '+%H:%M:%S') | Refresh: ${REFRESH_INTERVAL}s | Ctrl+C to exit${NC}\n"

        sleep "$REFRESH_INTERVAL"
    done
}

# Log a call
log_call() {
    local agent=$1
    echo "${agent}:$(date '+%Y-%m-%d %H:%M:%S')" >> "$CALL_LOG"
}

# Clear log
clear_log() {
    > "$CALL_LOG"
    echo "Log cleared."
}

# Command handling
case "${1:-}" in
    log)
        log_call "${2:-unknown}"
        ;;
    clear)
        clear_log
        ;;
    *)
        main
        ;;
esac

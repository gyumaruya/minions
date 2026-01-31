#!/usr/bin/env bash
# Agent Wrapper - Logs API calls and forwards to actual CLI
# Usage: agent-wrapper.sh <agent> [args...]
#   agent: claude, codex, gemini, copilot

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Use project-relative path or CLAUDE_PROJECT_DIR if set
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
LOG_DIR="${PROJECT_DIR}/.claude/logs"
CALL_LOG="${LOG_DIR}/agent-calls.log"

mkdir -p "$LOG_DIR" 2>/dev/null || true

log_call() {
    local agent=$1
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${agent}:${timestamp}" >> "$CALL_LOG"
}

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <agent> [args...]"
    echo "  agent: claude, codex, gemini, copilot"
    exit 1
fi

AGENT=$1
shift

case "$AGENT" in
    claude)
        log_call "claude"
        exec claude "$@"
        ;;
    codex)
        log_call "codex"
        exec codex "$@"
        ;;
    gemini)
        log_call "gemini"
        exec gemini "$@"
        ;;
    copilot)
        log_call "copilot"
        exec copilot "$@"
        ;;
    *)
        echo "Unknown agent: $AGENT"
        echo "Supported: claude, codex, gemini, copilot"
        exit 1
        ;;
esac

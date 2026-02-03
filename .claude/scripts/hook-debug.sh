#!/bin/bash
# Hook Debug Mode Manager
#
# Usage:
#   ./hook-debug.sh enable   - Enable debug logging
#   ./hook-debug.sh disable  - Disable debug logging
#   ./hook-debug.sh status   - Show current status
#   ./hook-debug.sh tail     - Tail the debug log
#   ./hook-debug.sh clear    - Clear the debug log
#   ./hook-debug.sh view     - View recent log entries (last 50)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
MARKER_FILE="$PROJECT_DIR/.claude/.hook-debug"
LOG_FILE="$PROJECT_DIR/.claude/logs/hook-debug.jsonl"

case "$1" in
    enable)
        touch "$MARKER_FILE"
        mkdir -p "$(dirname "$LOG_FILE")"
        echo "✅ Hook debug mode enabled"
        echo "   Marker: $MARKER_FILE"
        echo "   Log: $LOG_FILE"
        ;;
    disable)
        rm -f "$MARKER_FILE"
        echo "🔴 Hook debug mode disabled"
        ;;
    status)
        if [ -f "$MARKER_FILE" ]; then
            echo "✅ Hook debug mode: ENABLED"
        else
            echo "🔴 Hook debug mode: DISABLED"
        fi
        if [ -f "$LOG_FILE" ]; then
            lines=$(wc -l < "$LOG_FILE" | tr -d ' ')
            echo "   Log entries: $lines"
            echo "   Log file: $LOG_FILE"
        else
            echo "   Log file: (not created yet)"
        fi
        ;;
    tail)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE" | while read line; do
                echo "$line" | jq -c '{time: .timestamp, hook: .hook_name, tool: .tool_name, role: .agent_role, decision: .decision, reason: .reason}'
            done
        else
            echo "Log file not found: $LOG_FILE"
            echo "Enable debug mode first: $0 enable"
        fi
        ;;
    clear)
        if [ -f "$LOG_FILE" ]; then
            > "$LOG_FILE"
            echo "🗑️  Log cleared"
        else
            echo "Log file not found"
        fi
        ;;
    view)
        if [ -f "$LOG_FILE" ]; then
            echo "=== Recent Hook Debug Log (last 50 entries) ==="
            tail -50 "$LOG_FILE" | while read line; do
                echo "$line" | jq -c '{time: .timestamp[11:19], hook: .hook_name, tool: .tool_name, role: .agent_role, decision: .decision, reason: .reason}'
            done
        else
            echo "Log file not found: $LOG_FILE"
            echo "Enable debug mode first: $0 enable"
        fi
        ;;
    *)
        echo "Hook Debug Mode Manager"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  enable   - Enable debug logging"
        echo "  disable  - Disable debug logging"
        echo "  status   - Show current status"
        echo "  tail     - Tail the debug log (live)"
        echo "  clear    - Clear the debug log"
        echo "  view     - View recent log entries (last 50)"
        ;;
esac

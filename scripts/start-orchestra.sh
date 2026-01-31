#!/usr/bin/env bash
# Multi-Agent Orchestra Startup Script
# Launches tmux with Claude Code on the left and dashboard on the right

set -euo pipefail

# Configuration
SESSION_NAME="${ORCHESTRA_SESSION:-orchestra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    local missing=()

    if ! command -v tmux &>/dev/null; then
        missing+=("tmux")
    fi

    if ! command -v claude &>/dev/null; then
        missing+=("claude (Claude Code CLI)")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing[*]}"
        echo ""
        echo "Install them with:"
        echo "  brew install tmux"
        echo "  npm install -g @anthropic-ai/claude-code"
        exit 1
    fi
}

# Kill existing session if requested
cleanup_session() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        log_warn "Session '$SESSION_NAME' already exists."
        read -p "Kill existing session and start fresh? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            tmux kill-session -t "$SESSION_NAME"
            log_info "Killed existing session."
        else
            log_info "Attaching to existing session..."
            tmux attach-session -t "$SESSION_NAME"
            exit 0
        fi
    fi
}

# Create tmux session with layout
create_session() {
    log_info "Creating tmux session: $SESSION_NAME"

    # Create new session in detached mode, starting in project directory
    tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"

    # Split horizontally (left: 70%, right: 30%)
    tmux split-window -h -p 30 -c "$PROJECT_DIR"

    # Select left pane (pane 0) and start Claude Code
    tmux select-pane -t 0
    tmux send-keys -t 0 "cd '$PROJECT_DIR' && claude" Enter

    # Select right pane (pane 1) and start dashboard
    tmux select-pane -t 1
    tmux send-keys -t 1 "cd '$PROJECT_DIR' && bash scripts/dashboard.sh" Enter

    # Focus on left pane (Claude Code)
    tmux select-pane -t 0

    log_success "Session created successfully!"
}

# Print usage help
print_help() {
    echo "Multi-Agent Orchestra Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -k, --kill     Kill existing session before starting"
    echo "  -n, --name     Session name (default: orchestra)"
    echo "  -d, --detach   Don't attach to session after creation"
    echo ""
    echo "Layout:"
    echo "  ┌─────────────────────┬───────────────┐"
    echo "  │                     │               │"
    echo "  │    Claude Code      │   Dashboard   │"
    echo "  │       (70%)         │     (30%)     │"
    echo "  │                     │               │"
    echo "  └─────────────────────┴───────────────┘"
    echo ""
    echo "Tmux keybindings:"
    echo "  Ctrl+b %     Split pane vertically"
    echo "  Ctrl+b \"     Split pane horizontally"
    echo "  Ctrl+b o     Switch between panes"
    echo "  Ctrl+b x     Close current pane"
    echo "  Ctrl+b d     Detach from session"
    echo "  Ctrl+b z     Toggle pane zoom"
    echo ""
}

# Main
main() {
    local kill_existing=false
    local detach=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_help
                exit 0
                ;;
            -k|--kill)
                kill_existing=true
                shift
                ;;
            -n|--name)
                if [[ $# -lt 2 || -z "${2:-}" ]]; then
                    log_error "Missing session name for $1"
                    print_help
                    exit 1
                fi
                SESSION_NAME="$2"
                shift 2
                ;;
            -d|--detach)
                detach=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                print_help
                exit 1
                ;;
        esac
    done

    log_info "Starting Multi-Agent Orchestra..."
    echo ""

    # Check dependencies
    check_dependencies

    # Handle existing session
    if [[ "$kill_existing" == true ]]; then
        if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            tmux kill-session -t "$SESSION_NAME"
            log_info "Killed existing session."
        fi
    else
        cleanup_session
    fi

    # Create new session
    create_session

    # Attach to session
    if [[ "$detach" == false ]]; then
        log_info "Attaching to session... (Ctrl+b d to detach)"
        tmux attach-session -t "$SESSION_NAME"
    else
        log_success "Session created in background. Attach with: tmux attach -t $SESSION_NAME"
    fi
}

main "$@"

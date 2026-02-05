#!/usr/bin/env bash
# Recursion Guard: Prevent infinite loops in hooks
# Note: Copilot CLI itself doesn't trigger Claude hooks, so this is mainly for safety

set -uo pipefail

# Lock directory for recursion prevention
LOCK_DIR="${TMPDIR:-/tmp}/claude-hook-locks"

# Initialize lock directory
init_lock_dir() {
    mkdir -p "$LOCK_DIR"
}

# Acquire a lock to prevent recursion
# Returns 0 if lock acquired, 1 if already locked (recursion detected)
#
# Args:
#   $1: Lock name (e.g., "permission-request", "notification")
#   $2: (Optional) Timeout in seconds (default: 60)
acquire_lock() {
    local lock_name="$1"
    local timeout="${2:-60}"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    init_lock_dir

    # Check if lock exists and is recent
    if [[ -f "$lock_file" ]]; then
        local lock_time
        lock_time="$(cat "$lock_file" 2>/dev/null || echo "0")"
        local current_time
        current_time="$(date +%s)"
        local age=$((current_time - lock_time))

        if [[ $age -lt $timeout ]]; then
            # Lock is still valid, recursion detected
            return 1
        fi
        # Lock is stale, remove it
        rm -f "$lock_file"
    fi

    # Create lock
    date +%s > "$lock_file"
    return 0
}

# Release a lock
#
# Args:
#   $1: Lock name
release_lock() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"
    rm -f "$lock_file"
}

# Check if a lock is held (without acquiring)
#
# Args:
#   $1: Lock name
# Returns:
#   0 if locked, 1 if not locked
is_locked() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ -f "$lock_file" ]]; then
        local lock_time
        lock_time="$(cat "$lock_file" 2>/dev/null || echo "0")"
        local current_time
        current_time="$(date +%s)"
        local age=$((current_time - lock_time))

        if [[ $age -lt 60 ]]; then
            return 0  # Locked
        fi
    fi
    return 1  # Not locked
}

# Clean up stale locks (older than 5 minutes)
cleanup_stale_locks() {
    init_lock_dir

    local current_time
    current_time="$(date +%s)"
    local stale_threshold=300  # 5 minutes

    for lock_file in "$LOCK_DIR"/*.lock; do
        if [[ -f "$lock_file" ]]; then
            local lock_time
            lock_time="$(cat "$lock_file" 2>/dev/null || echo "0")"
            local age=$((current_time - lock_time))

            if [[ $age -gt $stale_threshold ]]; then
                rm -f "$lock_file"
            fi
        fi
    done
}

# Guard wrapper: Execute command only if not in recursion
# Usage: guarded_exec "lock_name" command args...
guarded_exec() {
    local lock_name="$1"
    shift

    if ! acquire_lock "$lock_name"; then
        # Recursion detected, skip execution
        return 0
    fi

    # Execute command
    local result=0
    "$@" || result=$?

    # Release lock
    release_lock "$lock_name"

    return $result
}

#!/usr/bin/env bats
# tests/setup-global-config.bats
# Test suite for setup-global-config.sh

# Temporary directory for testing
export TEST_TEMP_DIR=""

# Setup: executed before each test
setup() {
    # Create temporary directory
    TEST_TEMP_DIR=$(mktemp -d)

    # Test minions directory
    export TEST_MINIONS_DIR="$TEST_TEMP_DIR/minions"
    export TEST_HOME="$TEST_TEMP_DIR/home"

    mkdir -p "$TEST_MINIONS_DIR"
    mkdir -p "$TEST_HOME"

    # Override environment variables
    export MINIONS_DIR="$TEST_MINIONS_DIR"
    export HOME="$TEST_HOME"

    # Create .claude directory structure
    mkdir -p "$TEST_MINIONS_DIR/.claude/memory"

    # Create hooks-rs directory structure
    mkdir -p "$TEST_MINIONS_DIR/hooks-rs/target/release"

    # Create dummy hook binaries
    touch "$TEST_MINIONS_DIR/hooks-rs/target/release/load-memories"
    touch "$TEST_MINIONS_DIR/hooks-rs/target/release/auto-learn"
    chmod +x "$TEST_MINIONS_DIR/hooks-rs/target/release/load-memories"
    chmod +x "$TEST_MINIONS_DIR/hooks-rs/target/release/auto-learn"
}

# Cleanup: executed after each test
teardown() {
    if [ -n "$TEST_TEMP_DIR" ] && [ -d "$TEST_TEMP_DIR" ]; then
        rm -rf "$TEST_TEMP_DIR"
    fi
}

# ===============================
# Basic functionality tests
# ===============================

@test "script exists" {
    [ -f "scripts/setup-global-config.sh" ]
}

@test "script is executable" {
    [ -x "scripts/setup-global-config.sh" ]
}

@test "success: directory structure is created" {
    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]
    [ -d "$HOME/.config/ai/hooks" ]
    [ -d "$HOME/.config/ai/memory" ]
}

@test "success: symlink to hook binaries is created" {
    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]
    [ -L "$HOME/.config/ai/hooks/bin" ]

    # Verify symlink target
    LINK_TARGET=$(readlink "$HOME/.config/ai/hooks/bin")
    [ "$LINK_TARGET" = "$TEST_MINIONS_DIR/hooks-rs/target/release" ]
}

@test "success: empty global memory is created" {
    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]
    [ -f "$HOME/.config/ai/memory/events.jsonl" ]
}

@test "success: global Claude settings.json is created" {
    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]
    [ -f "$HOME/.claude/settings.json" ]

    # Verify JSON is valid (parseable by jq)
    if command -v jq >/dev/null 2>&1; then
        run jq -e . "$HOME/.claude/settings.json"
        [ "$status" -eq 0 ]
    fi
}

@test "memory migration: existing memory is migrated to global" {
    # Create existing memory
    echo '{"type":"test","content":"test memory"}' > "$TEST_MINIONS_DIR/.claude/memory/events.jsonl"

    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]
    [ -f "$HOME/.config/ai/memory/events.jsonl" ]

    # Verify content was migrated
    grep -q "test memory" "$HOME/.config/ai/memory/events.jsonl"
}

@test "memory migration: skip if global memory already exists" {
    # Create global memory first
    mkdir -p "$HOME/.config/ai/memory"
    echo '{"type":"existing","content":"existing memory"}' > "$HOME/.config/ai/memory/events.jsonl"

    # Create minions memory
    echo '{"type":"test","content":"test memory"}' > "$TEST_MINIONS_DIR/.claude/memory/events.jsonl"

    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]

    # Verify existing memory is preserved and not overwritten
    grep -q "existing memory" "$HOME/.config/ai/memory/events.jsonl"
    ! grep -q "test memory" "$HOME/.config/ai/memory/events.jsonl"
}

@test "backup: existing settings.json is backed up" {
    # Create existing settings.json
    mkdir -p "$HOME/.claude"
    echo '{"existing":"config"}' > "$HOME/.claude/settings.json"

    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]

    # Verify backup file was created (pattern match)
    run ls "$HOME/.claude"/settings.json.backup.*
    [ "$status" -eq 0 ]

    # Verify backup contains original content
    BACKUP_FILE=$(ls "$HOME/.claude"/settings.json.backup.* | head -1)
    grep -q "existing" "$BACKUP_FILE"
}

@test "symlink: recreate if existing link exists" {
    # Create symlink beforehand
    mkdir -p "$HOME/.config/ai/hooks"
    ln -sf "/tmp/dummy" "$HOME/.config/ai/hooks/bin"

    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]

    # Verify new link points to correct target
    LINK_TARGET=$(readlink "$HOME/.config/ai/hooks/bin")
    [ "$LINK_TARGET" = "$TEST_MINIONS_DIR/hooks-rs/target/release" ]
}

# ===============================
# Error case tests
# ===============================

@test "error: minions directory does not exist" {
    # Delete minions directory
    rm -rf "$TEST_MINIONS_DIR"

    run scripts/setup-global-config.sh

    [ "$status" -eq 1 ]
    [[ "$output" == *"minions ディレクトリが見つかりません"* ]]
}

@test "error: hook binaries not found" {
    # Delete hooks-rs directory
    rm -rf "$TEST_MINIONS_DIR/hooks-rs/target/release"

    run scripts/setup-global-config.sh

    [ "$status" -eq 1 ]
    [[ "$output" == *"フックバイナリが見つかりません"* ]]
}

# ===============================
# Integration tests
# ===============================

@test "integration: complete execution flow" {
    # Prepare existing memory and settings
    echo '{"type":"integration","content":"integration test"}' > "$TEST_MINIONS_DIR/.claude/memory/events.jsonl"

    run scripts/setup-global-config.sh

    [ "$status" -eq 0 ]

    # Verify all files and directories are created
    [ -d "$HOME/.config/ai/hooks" ]
    [ -d "$HOME/.config/ai/memory" ]
    [ -L "$HOME/.config/ai/hooks/bin" ]
    [ -f "$HOME/.config/ai/memory/events.jsonl" ]
    [ -f "$HOME/.claude/settings.json" ]

    # Verify memory content
    grep -q "integration test" "$HOME/.config/ai/memory/events.jsonl"

    # Verify settings.json validity
    if command -v jq >/dev/null 2>&1; then
        # Verify hook configuration exists
        run jq -e '.hooks.UserPromptSubmit' "$HOME/.claude/settings.json"
        [ "$status" -eq 0 ]

        run jq -e '.hooks.PreToolUse' "$HOME/.claude/settings.json"
        [ "$status" -eq 0 ]

        run jq -e '.hooks.PostToolUse' "$HOME/.claude/settings.json"
        [ "$status" -eq 0 ]
    fi
}

@test "integration: safe to run multiple times" {
    # First run
    run scripts/setup-global-config.sh
    [ "$status" -eq 0 ]

    # Second run
    run scripts/setup-global-config.sh
    [ "$status" -eq 0 ]

    # Verify files exist properly
    [ -d "$HOME/.config/ai/hooks" ]
    [ -L "$HOME/.config/ai/hooks/bin" ]
    [ -f "$HOME/.config/ai/memory/events.jsonl" ]
    [ -f "$HOME/.claude/settings.json" ]
}

#!/usr/bin/env bash
# Install Python hooks as symlinks in global hooks directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$PROJECT_DIR/resources/hooks"
GLOBAL_HOOKS_BIN="$HOME/.config/ai/hooks/bin"

echo "🔗 Installing Python hooks as symlinks..."
mkdir -p "$GLOBAL_HOOKS_BIN"

# Create symlinks for Python hooks (skip if Rust binary exists)
for hook in "$HOOKS_DIR"/*.py; do
    hook_name=$(basename "$hook" .py)
    target="$GLOBAL_HOOKS_BIN/$hook_name"

    # Skip if Rust binary already exists
    if [ -f "$target" ]; then
        if [ -L "$target" ]; then
            echo "  ← $hook_name (removing old symlink)"
            rm -f "$target"
        else
            echo "  ⊘ $hook_name (Rust version exists, skipping)"
            continue
        fi
    fi

    # Create symlink
    ln -s "$hook" "$target"
    echo "  ✓ $hook_name -> $hook"
done

echo "✅ Python hooks installed!"
echo "📍 Symlinks created in: $GLOBAL_HOOKS_BIN"

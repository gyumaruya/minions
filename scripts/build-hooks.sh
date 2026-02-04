#!/usr/bin/env bash
# Build Rust hooks and deploy to global hooks directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_RS_DIR="$PROJECT_DIR/resources/hooks-rs"
GLOBAL_HOOKS_BIN="$HOME/.config/ai/hooks/bin"

echo "🔨 Building Rust hooks..."
cd "$HOOKS_RS_DIR"

# Build in release mode
cargo build --release

echo "📦 Deploying hooks to $GLOBAL_HOOKS_BIN..."
mkdir -p "$GLOBAL_HOOKS_BIN"

# Copy all built binaries (executable files only, exclude .d files and libraries)
for binary in target/release/*; do
    # Skip if not a file or not executable
    [ -f "$binary" ] && [ -x "$binary" ] || continue

    # Skip .d files, .rlib files
    [[ "$binary" == *.d ]] && continue
    [[ "$binary" == *.rlib ]] && continue

    # Get basename
    basename=$(basename "$binary")

    # Skip build artifacts directories
    [[ "$basename" == "build" ]] && continue
    [[ "$basename" == "deps" ]] && continue
    [[ "$basename" == "examples" ]] && continue
    [[ "$basename" == "incremental" ]] && continue

    # Remove existing file/symlink and copy
    rm -f "$GLOBAL_HOOKS_BIN/$basename"
    cp "$binary" "$GLOBAL_HOOKS_BIN/"
    echo "  ✓ Deployed: $basename"
done

echo "✅ Build and deployment complete!"
echo "📍 Hooks deployed to: $GLOBAL_HOOKS_BIN"

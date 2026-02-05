#!/usr/bin/env bash
# Install hook binaries to ~/.config/ai/hooks/bin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/target/release"
DEST_DIR="$HOME/.config/ai/hooks/bin"

# Create destination directory
mkdir -p "$DEST_DIR"

# Find and copy only executable binaries (exclude .d, .rlib, etc.)
echo "Installing hooks..."
count=0
for file in "$SOURCE_DIR"/*; do
    basename=$(basename "$file")

    # Skip directories
    [ -d "$file" ] && continue

    # Skip files with extensions (like .d, .rlib)
    [[ "$basename" == *.* ]] && continue

    # Skip if not executable
    [ -x "$file" ] || continue

    # Copy executable to destination
    cp "$file" "$DEST_DIR/"
    count=$((count + 1))
    echo "  ✓ $basename"
done

echo ""
echo "✓ Installed $count hook binaries to $DEST_DIR"

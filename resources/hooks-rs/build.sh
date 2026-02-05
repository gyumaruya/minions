#!/usr/bin/env bash
# Build and install all hooks

set -e

echo "Building all hooks..."
cargo build --release --workspace

echo ""
echo "Installing hooks..."
./install-hooks.sh

echo ""
echo "✓ Build and install complete!"

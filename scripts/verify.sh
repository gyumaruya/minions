#!/usr/bin/env bash
# Verification script: Check code changes and run quality checks

set -uo pipefail  # Removed -e to allow collecting all errors

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🔍 検証を開始します..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Failure tracking
FAILED=0

# Git status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Git Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! git status --short; then
    echo -e "${YELLOW}⚠️  Git status failed${NC}"
fi
echo ""

# Git diff summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 変更差分"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! git diff --stat; then
    echo -e "${YELLOW}⚠️  No changes${NC}"
fi
echo ""

# Lint check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Lint Check (ruff)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if uv run ruff check . 2>&1; then
    echo -e "${GREEN}✅ Lint passed${NC}"
else
    echo -e "${RED}❌ Lint failed${NC}"
    FAILED=1
fi
echo ""

# Format check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📐 Format Check (ruff)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if uv run ruff format --check . 2>&1; then
    echo -e "${GREEN}✅ Format passed${NC}"
else
    echo -e "${YELLOW}⚠️  Format check failed (run: ruff format .)${NC}"
    FAILED=1
fi
echo ""

# Type check (optional - only if ty is available)
if uv run ty --version &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Type Check (ty)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if uv run ty check src/ 2>&1; then
        echo -e "${GREEN}✅ Type check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Type check failed${NC}"
        FAILED=1
    fi
    echo ""
fi

# Test (optional - only if tests exist)
if [ -d "tests" ] && [ "$(ls -A tests)" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Tests (pytest)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if uv run pytest tests/ -v 2>&1; then
        echo -e "${GREEN}✅ Tests passed${NC}"
    else
        echo -e "${RED}❌ Tests failed${NC}"
        FAILED=1
    fi
    echo ""
fi

# AI Verification (optional - call Copilot for analysis)
if command -v copilot &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🤖 AI 検証 (Copilot)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    PROMPT="サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

# 検証タスク

以下を確認して、簡潔に報告してください:

1. git status, git diff で変更内容を確認
2. 未完了タスクがないか確認
3. 問題点や改善点を指摘

## 出力形式（5行以内）

✅ **完了**: [確認内容]
⚠️ **注意**: [問題点]
💡 **提案**: [改善案]
"

    copilot -p "$PROMPT" --model claude-sonnet-4 --allow-all --silent 2>/dev/null || echo -e "${YELLOW}⚠️  Copilot verification skipped${NC}"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo "✨ 検証完了: すべて成功"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
else
    echo "❌ 検証失敗: 上記のエラーを修正してください"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi

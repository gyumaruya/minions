#!/bin/bash
# setup-global-config.sh
# minions のフックと記憶をグローバル化するセットアップスクリプト

set -e

MINIONS_DIR="${MINIONS_DIR:-$HOME/minions}"
GLOBAL_AI_DIR="$HOME/.config/ai"
GLOBAL_CLAUDE_DIR="$HOME/.claude"

echo "=== minions グローバル設定セットアップ ==="
echo ""
echo "minions ディレクトリ: $MINIONS_DIR"
echo "グローバル AI 設定:   $GLOBAL_AI_DIR"
echo "グローバル Claude:    $GLOBAL_CLAUDE_DIR"
echo ""

# 1. minions ディレクトリの確認
if [ ! -d "$MINIONS_DIR" ]; then
    echo "ERROR: minions ディレクトリが見つかりません: $MINIONS_DIR"
    echo "MINIONS_DIR 環境変数で指定してください"
    exit 1
fi

if [ ! -d "$MINIONS_DIR/hooks-rs/target/release" ]; then
    echo "ERROR: フックバイナリが見つかりません"
    echo "先に hooks-rs をビルドしてください: cd $MINIONS_DIR/hooks-rs && cargo build --release"
    exit 1
fi

# 2. グローバルディレクトリ構造の作成
echo "[1/5] ディレクトリ構造を作成..."
mkdir -p "$GLOBAL_AI_DIR/hooks"
mkdir -p "$GLOBAL_AI_DIR/memory"
mkdir -p "$GLOBAL_CLAUDE_DIR"

# 3. フックバイナリへのシンボリックリンク
echo "[2/5] フックバイナリをリンク..."
if [ -L "$GLOBAL_AI_DIR/hooks/bin" ]; then
    rm "$GLOBAL_AI_DIR/hooks/bin"
fi
ln -sf "$MINIONS_DIR/hooks-rs/target/release" "$GLOBAL_AI_DIR/hooks/bin"
echo "  -> $GLOBAL_AI_DIR/hooks/bin -> $MINIONS_DIR/hooks-rs/target/release"

# 4. 記憶の移行（既存があれば）
echo "[3/5] 記憶を移行..."
if [ -f "$MINIONS_DIR/.claude/memory/events.jsonl" ]; then
    if [ ! -f "$GLOBAL_AI_DIR/memory/events.jsonl" ]; then
        cp "$MINIONS_DIR/.claude/memory/events.jsonl" "$GLOBAL_AI_DIR/memory/events.jsonl"
        echo "  -> minions の記憶をグローバルに移行しました"
    else
        echo "  -> グローバル記憶が既に存在します（スキップ）"
    fi
else
    touch "$GLOBAL_AI_DIR/memory/events.jsonl"
    echo "  -> 空のグローバル記憶を作成しました"
fi

# 5. グローバル Claude settings.json の作成
echo "[4/5] グローバル Claude 設定を作成..."

# 既存の settings.json をバックアップ
if [ -f "$GLOBAL_CLAUDE_DIR/settings.json" ]; then
    BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$GLOBAL_CLAUDE_DIR/settings.json.backup.$BACKUP_TIME"
    cp "$GLOBAL_CLAUDE_DIR/settings.json" "$BACKUP_FILE"
    echo "  -> ⚠ 既存設定をバックアップ"
    echo "     保存先: $BACKUP_FILE"
    echo "     既存設定は新しい設定に上書きされます"
fi

# プラグイン設定を保持しつつ、フックを追加
cat > "$GLOBAL_CLAUDE_DIR/settings.json" << 'SETTINGS_EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "enabledPlugins": {
    "rust-analyzer-lsp@claude-plugins-official": true
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/load-memories\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/auto-learn\"",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|Task|WebFetch|WebSearch",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/pre-tool-recall\"",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/prevent-secrets-commit\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-japanese\"",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|Edit|Write|Task|WebFetch|WebSearch",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/post-tool-record\"",
            "timeout": 5
          }
        ]
      }
    ]
  },
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./**/*.pem)",
      "Read(./**/*.key)",
      "Read(./**/credentials*)",
      "Read(./**/*secret*)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Bash(rm -rf /)",
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~)",
      "Bash(sudo rm -rf *)"
    ]
  }
}
SETTINGS_EOF

echo "  -> グローバル設定を作成しました"

# 6. minions のローカル設定からフックを分離
echo "[5/5] minions のローカル設定を更新..."

# フック定義をバックアップ
if [ -f "$MINIONS_DIR/.claude/settings.json" ]; then
    BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$MINIONS_DIR/.claude/settings.json.pre-global-backup.$BACKUP_TIME"
    cp "$MINIONS_DIR/.claude/settings.json" "$BACKUP_FILE"
    echo "  -> ⚠ minions ローカル設定をバックアップ"
    echo "     保存先: $BACKUP_FILE"
    echo "     グローバルフックを参照するよう更新してください"
fi

echo ""
echo "=========================================="
echo "✅ セットアップ完了"
echo "=========================================="
echo ""
echo "📁 作成・更新されたファイル:"
echo ""
echo "  グローバル AI 設定 ($GLOBAL_AI_DIR):"
echo "    ├── hooks/bin -> フックバイナリ (symlink)"
echo "    └── memory/events.jsonl -> グローバル記憶"
echo ""
echo "  グローバル Claude 設定 ($GLOBAL_CLAUDE_DIR):"
echo "    ├── settings.json ✨ (新規作成 or 上書き)"
echo "    └── settings.json.backup.* (タイムスタンプ付き)"
echo ""
echo "💾 バックアップ:"
if [ -d "$GLOBAL_CLAUDE_DIR" ]; then
    BACKUP_COUNT=$(find "$GLOBAL_CLAUDE_DIR" -name "settings.json.backup.*" 2>/dev/null | wc -l)
    if [ $BACKUP_COUNT -gt 0 ]; then
        echo "    ✓ グローバル設定: $BACKUP_COUNT 個のバックアップを保存済み"
    fi
fi
if [ -d "$MINIONS_DIR/.claude" ]; then
    BACKUP_COUNT=$(find "$MINIONS_DIR/.claude" -name "settings.json.pre-global-backup.*" 2>/dev/null | wc -l)
    if [ $BACKUP_COUNT -gt 0 ]; then
        echo "    ✓ ローカル設定: $BACKUP_COUNT 個のバックアップを保存済み"
    fi
fi
echo ""
echo "⚙️  次のステップ:"
echo ""
echo "  1️⃣  minions/.claude/settings.json を確認"
echo "    - グローバルフック設定との重複を削除"
echo "    - プロジェクト固有のフックのみ残す"
echo ""
echo "  2️⃣  フック設定がグローバル記憶を参照するよう確認"
echo "    - 現在: \$CLAUDE_PROJECT_DIR/.claude/memory/"
echo "    - 推奨: \$HOME/.config/ai/memory/"
echo ""
echo "  3️⃣  動作確認:"
echo ""
echo "    # グローバル設定を確認"
echo "    cat $GLOBAL_CLAUDE_DIR/settings.json"
echo ""
echo "    # グローバル記憶を確認"
echo "    cat $GLOBAL_AI_DIR/memory/events.jsonl"
echo ""
echo "    # ディレクトリ構成を確認"
echo "    ls -la $GLOBAL_AI_DIR/"
echo ""
echo "=========================================="

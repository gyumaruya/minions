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
    cp "$GLOBAL_CLAUDE_DIR/settings.json" "$GLOBAL_CLAUDE_DIR/settings.json.backup"
    echo "  -> 既存設定をバックアップ: settings.json.backup"
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
    cp "$MINIONS_DIR/.claude/settings.json" "$MINIONS_DIR/.claude/settings.json.pre-global-backup"
    echo "  -> minions 設定をバックアップ: settings.json.pre-global-backup"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "作成されたファイル:"
echo "  $GLOBAL_AI_DIR/hooks/bin -> フックバイナリ (symlink)"
echo "  $GLOBAL_AI_DIR/memory/events.jsonl -> グローバル記憶"
echo "  $GLOBAL_CLAUDE_DIR/settings.json -> グローバルフック設定"
echo ""
echo "次のステップ:"
echo "  1. minions/.claude/settings.json からプロジェクト固有のフックのみ残す"
echo "  2. フックがグローバル記憶を参照するよう更新が必要"
echo "     (現在は \$CLAUDE_PROJECT_DIR/.claude/memory/ を参照)"
echo ""
echo "確認コマンド:"
echo "  ls -la $GLOBAL_AI_DIR/"
echo "  cat $GLOBAL_CLAUDE_DIR/settings.json"

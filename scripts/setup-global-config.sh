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

if [ ! -d "$MINIONS_DIR/resources/hooks-rs/target/release" ]; then
    echo "ERROR: フックバイナリが見つかりません"
    echo "先に hooks-rs をビルドしてください: cd $MINIONS_DIR/resources/hooks-rs && cargo build --release"
    exit 1
fi

# 2. グローバルディレクトリ構造の作成
echo "[1/8] ディレクトリ構造を作成..."
mkdir -p "$GLOBAL_AI_DIR/hooks"
mkdir -p "$GLOBAL_AI_DIR/memory"
mkdir -p "$GLOBAL_CLAUDE_DIR"

# 3. フックバイナリへのシンボリックリンク
echo "[2/8] フックバイナリをリンク..."
if [ -L "$GLOBAL_AI_DIR/hooks/bin" ]; then
    rm "$GLOBAL_AI_DIR/hooks/bin"
fi
ln -sf "$MINIONS_DIR/resources/hooks-rs/target/release" "$GLOBAL_AI_DIR/hooks/bin"
echo "  -> $GLOBAL_AI_DIR/hooks/bin -> $MINIONS_DIR/resources/hooks-rs/target/release"

# 4. スキルのシンボリックリンク（~/.claude/skills）
echo "[3/8] スキルをリンク..."
if [ -L "$GLOBAL_CLAUDE_DIR/skills" ]; then
    rm "$GLOBAL_CLAUDE_DIR/skills"
fi
if [ -d "$MINIONS_DIR/.claude/skills" ]; then
    ln -sf "$MINIONS_DIR/.claude/skills" "$GLOBAL_CLAUDE_DIR/skills"
    echo "  -> $GLOBAL_CLAUDE_DIR/skills -> $MINIONS_DIR/.claude/skills"
else
    echo "  -> ⚠ スキルディレクトリが見つかりません（スキップ）"
fi

# 5. エージェント設定のシンボリックリンク（~/.claude/agents）
echo "[4/8] エージェント設定をリンク..."
if [ -L "$GLOBAL_CLAUDE_DIR/agents" ]; then
    rm "$GLOBAL_CLAUDE_DIR/agents"
fi
if [ -d "$MINIONS_DIR/.claude/agents" ]; then
    ln -sf "$MINIONS_DIR/.claude/agents" "$GLOBAL_CLAUDE_DIR/agents"
    echo "  -> $GLOBAL_CLAUDE_DIR/agents -> $MINIONS_DIR/.claude/agents"
else
    echo "  -> ⚠ エージェントディレクトリが見つかりません（スキップ）"
fi

# 6. ルールのシンボリックリンク（~/.claude/rules）
echo "[5/8] ルールをリンク..."
if [ -L "$GLOBAL_CLAUDE_DIR/rules" ]; then
    rm "$GLOBAL_CLAUDE_DIR/rules"
fi
if [ -d "$MINIONS_DIR/.claude/rules" ]; then
    ln -sf "$MINIONS_DIR/.claude/rules" "$GLOBAL_CLAUDE_DIR/rules"
    echo "  -> $GLOBAL_CLAUDE_DIR/rules -> $MINIONS_DIR/.claude/rules"
else
    echo "  -> ⚠ ルールディレクトリが見つかりません（スキップ）"
fi

# 7. CLAUDE.md のシンボリックリンク（~/.claude/CLAUDE.md）
echo "[6/8] CLAUDE.md をリンク..."
if [ -L "$GLOBAL_CLAUDE_DIR/CLAUDE.md" ]; then
    rm "$GLOBAL_CLAUDE_DIR/CLAUDE.md"
fi
if [ -f "$MINIONS_DIR/CLAUDE.md" ]; then
    ln -sf "$MINIONS_DIR/CLAUDE.md" "$GLOBAL_CLAUDE_DIR/CLAUDE.md"
    echo "  -> $GLOBAL_CLAUDE_DIR/CLAUDE.md -> $MINIONS_DIR/CLAUDE.md"
else
    echo "  -> ⚠ CLAUDE.md が見つかりません（スキップ）"
fi

# 8. 記憶の移行（既存があれば）
echo "[7/8] 記憶を移行..."
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

# 9. グローバル Claude settings.json の作成
echo "[8/8] グローバル Claude 設定を作成..."

# 既存の settings.json をバックアップ
if [ -f "$GLOBAL_CLAUDE_DIR/settings.json" ]; then
    BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$GLOBAL_CLAUDE_DIR/settings.json.backup.$BACKUP_TIME"
    cp "$GLOBAL_CLAUDE_DIR/settings.json" "$BACKUP_FILE"
    echo "  -> ⚠ 既存設定をバックアップ"
    echo "     保存先: $BACKUP_FILE"
    echo "     既存設定は新しい設定に上書きされます"
fi

# フル設定を作成（全23フック）
cat > "$GLOBAL_CLAUDE_DIR/settings.json" << 'SETTINGS_EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "EDITOR": "code --wait"
  },
  "permissions": {
    "allow": [
      "Read(*)",
      "Edit(*)",
      "Write(*)",
      "MultiEdit(*)",
      "Glob(*)",
      "Grep(*)",
      "LS(*)",
      "WebFetch(*)",
      "WebSearch(*)",
      "Task(*)",
      "Skill(*)",
      "TodoRead(*)",
      "TodoWrite(*)",
      "Bash(*)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./**/*.pem)",
      "Read(./**/*.key)",
      "Read(./**/credentials*)",
      "Read(./**/*secret*)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Read(~/.config/gcloud/**)",
      "Bash(rm -rf /)",
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~)",
      "Bash(rm -rf ~/*)",
      "Bash(sudo rm -rf *)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/session-start\"",
            "timeout": 5
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/auto-create-pr\"",
            "timeout": 60
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/load-memories\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/auto-learn\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/agent-router\"",
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
            "command": "\"$HOME/.config/ai/hooks/bin/ensure-noreply-email\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-japanese\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-draft-pr\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-no-merge\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/prevent-secrets-commit\"",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-hierarchy\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/ensure-pr-open\"",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/check-codex-before-write\"",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "WebSearch|WebFetch",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/suggest-gemini-research\"",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write|Bash|WebFetch|WebSearch|Task",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/enforce-delegation\"",
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
      },
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/check-codex-after-plan\"",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/hierarchy-permissions\"",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/post-test-analysis\"",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/log-cli-tools\"",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/auto-commit-on-verify\"",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/lint-on-save\"",
            "timeout": 30
          },
          {
            "type": "command",
            "command": "\"$HOME/.config/ai/hooks/bin/post-implementation-review\"",
            "timeout": 10
          }
        ]
      }
    ]
  },
  "enabledPlugins": {
    "rust-analyzer-lsp@claude-plugins-official": true
  },
  "model": "sonnet"
}
SETTINGS_EOF

echo "  -> グローバル設定を作成しました"

# 10. minions のローカル設定からフックを分離
echo "[完了] minions のローカル設定を更新..."

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
echo "    ├── skills -> スキル (symlink)"
echo "    ├── agents -> エージェント設定 (symlink)"
echo "    ├── rules -> ルール (symlink)"
echo "    ├── CLAUDE.md -> プロジェクト指示書 (symlink)"
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

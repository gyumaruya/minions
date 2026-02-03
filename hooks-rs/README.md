# Rust Hooks for Claude Code

Claude Code のフックを Rust で実装したもの。Python 版より高速で、型安全。

## 概要

23個のフックを Rust に移植済み。

## ビルド

```bash
cd hooks-rs
cargo build --release
```

バイナリは `target/release/` に生成される。

## 設定

`.claude/settings.json` でフックを有効化:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/hooks-rs/target/release/enforce-delegation\""
          }
        ]
      }
    ]
  }
}
```

## 主要フック

### enforce-delegation

Conductor（メインセッション）が直接作業しすぎないよう制限。

**動作:**
- 作業ツール（Bash, Edit, Write, etc.）の連続使用をカウント
- 3回: 警告強化
- 5回: ブロック（Task で委譲が必要）

**ロール判定:**
- TTY あり → Conductor（メインセッション）
- TTY なし → Musician（サブエージェント、制限なし）

**Allowlist:**
- `.claude/` 配下はカウント外
- `memory/`, `pyproject.toml`, `settings.json` も許可

### enforce-hierarchy

階層に基づくファイル編集制限。

**動作:**
- Musician: すべてのファイルを編集可能
- Conductor: `.claude/` 配下のみ直接編集可能

## デバッグ

### デバッグモード有効化

```bash
# マーカーファイルを作成
touch .claude/.hook-debug

# または環境変数
export CLAUDE_HOOK_DEBUG=1
```

### ログ確認

```bash
# デバッグログ
cat .claude/logs/hook-debug.jsonl | jq .

# 最新10件
tail -10 .claude/logs/hook-debug.jsonl | jq -c '{hook: .hook_name, role: .agent_role, decision: .decision}'
```

### 状態ファイル

```bash
# 委譲カウンター
cat /tmp/claude-delegation-*.json | jq .
```

## アーキテクチャ

```
hooks-rs/
├── Cargo.toml              # ワークスペース定義
├── crates/
│   ├── hook-common/        # 共通ライブラリ
│   │   └── src/
│   │       ├── lib.rs      # プレリュード
│   │       ├── input.rs    # HookInput パーサー
│   │       ├── output.rs   # HookOutput ビルダー
│   │       └── debug.rs    # デバッグログ
│   └── hooks/              # 各フック実装
│       ├── enforce-delegation/
│       ├── enforce-hierarchy/
│       └── ... (21 more)
└── target/release/         # ビルド済みバイナリ
```

## 共通ライブラリ (hook-common)

### HookInput

```rust
let input = HookInput::from_stdin()?;
let tool_name = &input.tool_name;
let file_path = input.get_file_path();
```

### HookOutput

```rust
// 許可
HookOutput::allow().write_stdout()?;

// 許可 + メッセージ
HookOutput::allow().with_context("💡 ヒント").write_stdout()?;

// ブロック
HookOutput::deny().with_context("⛔ エラー").write_stdout()?;
```

### デバッグログ

```rust
use hook_common::prelude::*;

log_decision(
    "hook-name",
    tool_name,
    file_path,
    role,
    "allow",
    "理由"
);
```

## フック一覧

| フック名 | イベント | 説明 |
|---------|---------|------|
| auto-create-pr | UserPromptSubmit | PR 自動作成 |
| load-memories | UserPromptSubmit | 記憶読み込み |
| auto-learn | UserPromptSubmit | 自動学習 |
| agent-router | UserPromptSubmit | エージェントルーティング |
| pre-tool-recall | PreToolUse | ツール前リコール |
| ensure-noreply-email | PreToolUse:Bash | noreply メール強制 |
| enforce-japanese | PreToolUse:Bash | 日本語強制 |
| enforce-draft-pr | PreToolUse:Bash | ドラフト PR 強制 |
| enforce-no-merge | PreToolUse:Bash | マージ禁止 |
| prevent-secrets-commit | PreToolUse:Bash | シークレット検出 |
| enforce-hierarchy | PreToolUse:Edit/Write | 階層制限 |
| ensure-pr-open | PreToolUse:Edit/Write | PR オープン確認 |
| check-codex-before-write | PreToolUse:Edit/Write | Codex 事前確認 |
| suggest-gemini-research | PreToolUse:Web* | Gemini 推奨 |
| enforce-delegation | PreToolUse:* | 委譲強制 |
| post-tool-record | PostToolUse | ツール後記録 |
| check-codex-after-plan | PostToolUse:Task | Codex 事後確認 |
| hierarchy-permissions | PostToolUse:Task | 階層許可付与 |
| post-test-analysis | PostToolUse:Bash | テスト分析 |
| log-cli-tools | PostToolUse:Bash | CLI ログ |
| auto-commit-on-verify | PostToolUse:Bash | 自動コミット |
| lint-on-save | PostToolUse:Edit/Write | Lint 実行 |
| post-implementation-review | PostToolUse:Edit/Write | 実装レビュー |

## 今後の課題

- [ ] Musician → Musician 委譲の制限（現状は許可、様子見）
- [ ] Windows サポート（TTY 判定）
- [ ] パフォーマンス計測

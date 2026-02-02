# Rust Hooks

Claude Code hooks をRustで実装したプロジェクト。

## 目的

- **クロスプラットフォーム**: Mac, Linux, Windows で動作
- **安定性**: Python環境依存を排除、構文エラーリスクを低減
- **パフォーマンス**: 単一バイナリ、高速起動

## 構成

```
hooks-rs/
├── Cargo.toml              # ワークスペース設定
├── crates/
│   ├── hook-common/        # 共通ライブラリ
│   │   ├── src/
│   │   │   ├── lib.rs      # エントリポイント
│   │   │   ├── input.rs    # JSON stdin パース
│   │   │   ├── output.rs   # JSON stdout 出力
│   │   │   ├── state.rs    # /tmp 状態ファイル管理
│   │   │   └── subprocess.rs # シェルコマンド実行
│   │   └── Cargo.toml
│   └── hooks/              # 各hook実装
│       ├── enforce-no-merge/
│       ├── enforce-draft-pr/
│       ├── prevent-secrets-commit/
│       └── ensure-pr-open/
└── tests/
    └── fixtures/           # テストデータ (../tests/fixtures/hooks/)
```

## 実装済みHooks

### Tier 1 (単純 × 重要)

| Hook | 説明 | ステータス |
|------|------|-----------|
| enforce-no-merge | マージ操作をブロック | ✅ 完了 |
| enforce-draft-pr | draft PR を強制 | ✅ 完了 |
| prevent-secrets-commit | シークレット検出 | ✅ 完了 |
| ensure-pr-open | PR必須 | ✅ 完了 |

### Tier 2 (subprocess多用) - 未実装

| Hook | 説明 |
|------|------|
| lint-on-save | ruff/ty 実行 |
| auto-create-pr | セッション開始時PR作成 |
| auto-commit-on-verify | 検証成功時自動コミット |
| enforce-japanese | 日本語強制 |

### Tier 3 (状態管理) - 未実装

| Hook | 説明 |
|------|------|
| enforce-delegation | 委譲強制 |
| agent-router | エージェントルーティング |
| log-cli-tools | CLI呼び出しログ |

### Tier 4 (Memory依存) - 未実装

| Hook | 説明 |
|------|------|
| load-memories | 記憶読み込み |
| pre-tool-recall | ツール実行前リコール |
| post-tool-record | ツール実行後記録 |
| auto-learn | 自動学習 |

## ビルド

```bash
cd hooks-rs
cargo build --release
```

バイナリは `target/release/` に生成される。

## テスト

```bash
# ユニットテスト
cargo test

# E2Eテスト
cd /Users/takuya/minions
uv run python tests/test_rust_hooks.py
```

## 使い方

Claude Code の `.claude/settings.json` でhookパスを設定:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "command": "/path/to/hooks-rs/target/release/enforce-no-merge"
      }
    ]
  }
}
```

## hook-common API

### HookInput

```rust
use hook_common::prelude::*;

let input = HookInput::from_stdin()?;
if input.is_bash() {
    let command = input.get_command();
}
```

### HookOutput

```rust
// 許可
HookOutput::allow().write_stdout()?;

// 拒否
HookOutput::deny()
    .with_context("Blocked for security")
    .write_stdout()?;

// 確認要求
HookOutput::ask()
    .with_context("Are you sure?")
    .write_stdout()?;

// サイレントパス（何も出力しない）
// return Ok(());
```

### StateManager

```rust
use hook_common::state::StateManager;

let state = StateManager::new("my-hook");
state.save("key", &data)?;
let data: Option<MyState> = state.load("key")?;
```

### Subprocess

```rust
use hook_common::subprocess::{run_command, git, gh};

let result = run_command("ls -la")?;
let result = git("status --porcelain")?;
let result = gh("pr list --json number")?;
```

## 移行計画

1. ✅ テスト基盤構築（Python記録用ランナー）
2. ✅ hook-common クレート
3. ✅ Tier 1 hooks (4個)
4. 🔄 Tier 2-4 hooks
5. ⏳ hook-memory クレート
6. ⏳ CI/CD 設定

## ライセンス

MIT

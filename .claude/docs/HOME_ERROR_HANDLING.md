# HOME 環境変数未定義時のエラーハンドリング改善

## 概要

`hooks-rs/crates/hook-memory/src/storage.rs` における HOME 環境変数のエラーハンドリングを改善しました。

## 変更内容

### 1. `default_path()` の戻り値型を `Result` に変更

**Before:**
```rust
pub fn default_path() -> Utf8PathBuf {
    // フォールバック: 相対パス使用（不安定）
    if let Ok(custom_path) = std::env::var("AI_MEMORY_PATH") {
        return Utf8PathBuf::from(custom_path);
    }

    if let Some(home) = dirs_home() {
        Utf8PathBuf::from(format!("{}/.config/ai/memory/events.jsonl", home))
    } else {
        Utf8PathBuf::from(".config/ai/memory/events.jsonl")  // 相対パスにフォールバック
    }
}
```

**After:**
```rust
pub fn default_path() -> Result<Utf8PathBuf> {
    // Priority 1: 環境変数による上書き（優先度最高）
    if let Ok(custom_path) = std::env::var("AI_MEMORY_PATH") {
        return Ok(Utf8PathBuf::from(custom_path));
    }

    // Priority 2: OS標準設定ディレクトリ
    if let Some(config_dir) = dirs::config_dir() {
        if let Ok(utf8_path) = Utf8PathBuf::try_from(config_dir) {
            let memory_dir = utf8_path.join("ai/memory/events.jsonl");
            return Ok(memory_dir);
        }
    }

    // Priority 3: 明示的なエラー
    Err(anyhow!(
        "Failed to determine memory storage path. Please set one of:\n  \
        1. Environment variable: AI_MEMORY_PATH=/path/to/events.jsonl\n  \
        2. Environment variable: HOME (for config directory resolution)\n  \
        3. Environment variable: XDG_CONFIG_HOME (on Linux)"
    ))
}
```

### 2. 依存関係に `dirs` クレートを追加

**hooks-rs/Cargo.toml:**
```toml
[workspace.dependencies]
dirs = "5.0"
```

**hooks-rs/crates/hook-memory/Cargo.toml:**
```toml
[dependencies]
dirs.workspace = true
```

### 3. 呼び出し側の更新

`default_path()` が `Result` を返すようになったため、以下 4 つのファイルで呼び出し側を修正:

- `crates/hooks/load-memories/src/main.rs`
- `crates/hooks/post-tool-record/src/main.rs`
- `crates/hooks/pre-tool-recall/src/main.rs`
- `crates/hooks/auto-learn/src/main.rs`

パターン:
```rust
let storage_path = match MemoryStorage::default_path() {
    Ok(path) => path,
    Err(e) => {
        eprintln!("Warning: Failed to determine memory storage path: {}", e);
        // 各フックに応じた適切なエラー処理
        return Vec::new();  // または return false;
    }
};
let storage = MemoryStorage::new(storage_path);
```

## エラーメッセージの例

### シナリオ 1: AI_MEMORY_PATH が設定されている場合（最優先）

```bash
$ export AI_MEMORY_PATH=/tmp/my-memory/events.jsonl
$ # ✓ 成功 - /tmp/my-memory/events.jsonl が使用される
```

### シナリオ 2: OS設定ディレクトリが使用可能な場合（フォールバック）

```bash
$ unset AI_MEMORY_PATH
$ # macOS: ~/.config/ai/memory/events.jsonl が使用される
$ # Linux (XDG): $XDG_CONFIG_HOME/ai/memory/events.jsonl が使用される
$ # Windows: %APPDATA%\ai\memory\events.jsonl が使用される
```

### シナリオ 3: どちらも利用不可の場合（エラー）

```
Failed to determine memory storage path. Please set one of:
  1. Environment variable: AI_MEMORY_PATH=/path/to/events.jsonl
  2. Environment variable: HOME (for config directory resolution)
  3. Environment variable: XDG_CONFIG_HOME (on Linux)
```

## テスト

以下のテストを追加して検証:

1. **`test_default_path_with_env()`** - AI_MEMORY_PATH が設定されている場合
2. **`test_default_path_fallback_to_dirs()`** - OS設定ディレクトリへのフォールバック
3. **`test_storage_with_custom_path()`** - ネストされたディレクトリの作成

```bash
$ cargo test -p hook-memory
running 9 tests
test storage::tests::test_default_path_fallback_to_dirs ... ok
test storage::tests::test_default_path_with_env ... ok
test storage::tests::test_append_and_load ... ok
test storage::tests::test_search ... ok
test storage::tests::test_load_by_type ... ok
test storage::tests::test_storage_with_custom_path ... ok
...
test result: ok. 9 passed; 0 failed; 0 ignored
```

## 利点

| 項目 | 改善内容 |
|------|---------|
| **予測可能性** | 相対パス使用を廃止し、絶対パスのみ使用 |
| **OS互換性** | `dirs` クレートで各OS（macOS/Linux/Windows）の標準パスに対応 |
| **エラーハンドリング** | 失敗時に明確なエラーメッセージを提供 |
| **環境変数優先度** | AI_MEMORY_PATH による明示的なオーバーライドが可能 |
| **テスト環境対応** | AI_MEMORY_PATH でテスト用パスを簡単に指定可能 |

## 設計原則

Codex による設計レビュー結果に基づいて実装:

- ✓ **優先度ベース**: AI_MEMORY_PATH → OS設定ディレクトリ → エラー
- ✓ **結果型返却**: `Result<T, E>` で失敗を明示的に表現
- ✓ **予測不可能性を排除**: 相対パス使用を廃止
- ✓ **OS固有パス対応**: `dirs::config_dir()` で標準ディレクトリを取得

## 移行ガイド

### 既存コード

既存の呼び出し側は自動的にエラーハンドリングを追加済み。

以下のパターンで動作:

```rust
let storage_path = match MemoryStorage::default_path() {
    Ok(path) => path,
    Err(e) => {
        eprintln!("Warning: {}", e);
        return /* 適切なデフォルト値 */;
    }
};
```

### 新しいコード

将来のコード追加時も同じパターンを使用してください。

## 参考資料

- `dirs` クレート: https://docs.rs/dirs/
- Error Handling in Rust: https://doc.rust-lang.org/book/ch09-00-error-handling.html

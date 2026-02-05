# Verification System

**事後検証システム**: エージェントが自由に作業し、完了時に検証する新しいアプローチ。

## Overview

**旧システム**: 事前の権限制限 → 作業をブロック
**新システム**: 事後検証 → 自由に作業、完了時に検証

## Phase 1: 手動検証（現在）

### 使い方

```bash
./scripts/verify.sh
```

### 検証内容

1. **Git Status** - 変更ファイル確認
2. **Git Diff** - 差分サマリー
3. **Lint Check** - `ruff check .`
4. **Format Check** - `ruff format --check .`
5. **Type Check** - `ty check src/` (利用可能な場合)
6. **Tests** - `pytest tests/` (テストが存在する場合)
7. **AI 検証** - Copilot による分析（オプション）

### 検証タイミング

- 実装完了後、手動で実行
- コミット前の最終確認
- PR 作成前のチェック
- CI/CD パイプライン（exit code により失敗検知）

## Phase 2: 自動検証（計画中）

### アプローチ

**明示マーカー検出（PostAssistantResponse または代替手段）**:

1. エージェントが完了時に `[[VERIFY:done]]` マーカーを応答に含める
2. 検出フック（実装方法は要検討）:
   - **理想**: PostAssistantResponse フック（現在 Claude Code に存在しない）
   - **代替案1**: 手動トリガー（`/verify` スキル）
   - **代替案2**: コミット前フック（git pre-commit）
3. 自動的に検証エージェントを起動
4. 検証結果をコンテキストに追加

### 技術的制約

**重要**: `[[VERIFY:done]]` マーカーは**応答本文**に出現するため、PostToolUse フックでは検出できません。実装には以下のいずれかが必要:

- Claude Code 本体への PostAssistantResponse フック追加
- または、手動トリガー方式（`/verify` スキル）を継続
- または、git フックでの検証強制化

### エージェント指示

```markdown
完了時は必ず以下を応答に含める:
- 「作業完了しました [[VERIFY:done]]」
```

## Phase 3: 専用ツール（将来）

Claude Code 本体に専用ツールを追加:

```python
# 理想形
final_response("実装完了 [[VERIFY:done]]")
```

## 検証プロファイル

### Quick（デフォルト）

- Git status, diff
- 未完了タスク確認
- 簡易レポート（5行以内）

### Standard

- Quick の内容
- Lint/Format チェック
- 手動レビュー観点の提示

### Deep

- Standard の内容
- Type check 実行
- Test 実行
- セキュリティチェック

## 検証エージェント選定

| 状況 | エージェント | 理由 |
|------|-------------|------|
| デフォルト | Copilot (Sonnet 4 + Opus 4.5) | コスト効率 |
| 大規模変更 | Codex | 深い分析 |
| セキュリティ | Codex | 専門性 |
| 失敗再発 | Codex | 詳細デバッグ |

### エスカレーション条件

以下の場合は Codex にエスカレート:

- 変更ファイル数 > 10
- 差分行数 > 500
- テスト失敗
- セキュリティ関連ファイル変更
- 前回の検証で問題発見

## 削除された制限

以下の事前制限フックを削除:

1. **enforce-hierarchy** - Conductor の直接編集制限
2. **enforce-delegation** - 連続作業カウント制限
3. **hierarchy-permissions** - 階層型許可通知

## 利点

### 旧システム（事前制限）

- ❌ ワークフロー阻害
- ❌ 誤検知でブロック
- ❌ 過剰な介入
- ❌ 柔軟性なし

### 新システム（事後検証）

- ✅ 自由な作業
- ✅ 完了時のみ検証
- ✅ 誤検知最小化
- ✅ 柔軟な対応

## 使用例

### 通常ワークフロー

```bash
# 1. 実装作業
# ... (エージェントが自由に作業)

# 2. 検証実行
./scripts/verify.sh

# 3. 問題があれば修正
# ... (lint エラー修正など)

# 4. 再検証
./scripts/verify.sh

# 5. コミット
git add .
git commit -m "実装完了

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### CI/CD 統合

```yaml
# .github/workflows/verify.yml
- name: Verification
  run: ./scripts/verify.sh
```

## トラブルシューティング

### Copilot が見つからない

```bash
# Copilot なしで実行
./scripts/verify.sh
# AI 検証部分はスキップされます
```

### Lint エラー

```bash
# 自動修正
uv run ruff check --fix .
uv run ruff format .
```

### Test 失敗

```bash
# 詳細確認
uv run pytest tests/ -vv
```

## 今後の拡張

- [ ] Phase 2: 自動検証フック実装
- [ ] Phase 3: 専用ツール追加
- [ ] 検証履歴の記録
- [ ] 検証レポートの永続化
- [ ] プロファイル選択機能
- [ ] カスタムチェック追加

## 参考

- Codex 設計レビュー: `.claude/logs/cli-tools.jsonl`
- フック実装: `resources/hooks-rs/`
- スクリプト: `scripts/verify.sh`

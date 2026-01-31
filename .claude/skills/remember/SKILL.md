# remember

ユーザーからの指示・修正・学習を記憶として保存し、今後の自己改善に活用する。

## Trigger

- ユーザーが「覚えて」「記憶して」「remember」と言った時
- ユーザーから修正・指示を受けた時（自動で記録を検討）
- 「/remember」コマンド

## Usage

```
/remember <学習内容>
/remember list              # 記憶一覧
/remember search <キーワード>  # 検索
```

## Categories

- `user_preference` - ユーザーの好み（日本語で書く、など）
- `workflow` - ワークフローパターン（PR作成時は自動プッシュ、など）
- `design_decision` - 設計判断
- `error_pattern` - エラーと解決策
- `tool_usage` - ツールの使い方

## Implementation

<learn-skill>

1. **記憶の保存**

ユーザーの指示・修正を受けた時:

```python
import sys
sys.path.insert(0, "$CLAUDE_PROJECT_DIR/src")
from minions.memory import add_memory, CATEGORY_USER_PREFERENCE

# 学習を保存
add_memory(
    content="ユーザー向けコンテンツ（PR、コミット）は日本語で作成する",
    category=CATEGORY_USER_PREFERENCE,
    metadata={"source": "user_correction", "context": "PR was in English"}
)
```

2. **記憶の検索・活用**

タスク開始時に関連する記憶を検索:

```python
from minions.memory import search_memories, get_recent_memories

# 関連する学習を検索
learnings = search_memories("日本語", category="user_preference")

# 最近の学習を取得
recent = get_recent_memories(limit=5)
```

3. **記憶一覧の表示**

```bash
cat ~/.minions/.claude/memory/learnings.jsonl | jq -r '.content' | head -20
```

</learn-skill>

## Auto-Learning Triggers

以下の状況で自動的に学習を記録:

1. **ユーザー修正時** - 「〜にして」「〜は違う」などの指摘
2. **エラー解決時** - エラーパターンと解決策
3. **設計決定時** - Codex/Gemini との相談結果
4. **ワークフロー確立時** - 繰り返されるパターン

## Memory File

記憶は以下に保存:
```
~/.minions/.claude/memory/learnings.jsonl
```

各行がJSON形式の記憶レコード:
```json
{
  "id": "20260131174500123456",
  "content": "PRタイトルとコミットメッセージは日本語で書く",
  "category": "user_preference",
  "metadata": {"source": "user_correction"},
  "created_at": "2026-01-31T17:45:00"
}
```

## Examples

### 例1: ユーザーの好みを記録

ユーザー: 「PRは日本語にして」

→ 自動で記録:
```
content: "ユーザー向けコンテンツ（PR、コミット、エラーメッセージ）は日本語で記述する"
category: "user_preference"
```

### 例2: ワークフローを記録

ユーザー: 「コミットしたら自動でPR作成して」

→ 自動で記録:
```
content: "コミット後は自動でプッシュ・PR作成まで行う"
category: "workflow"
```

### 例3: エラーパターンを記録

エラー: `jj describe` でメールアドレスエラー

→ 自動で記録:
```
content: "Error: invalid email / Solution: noreply email を使用"
category: "error_pattern"
```

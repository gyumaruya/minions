# /delegate - タスク委譲スキル

<command-name>delegate</command-name>

<description>
上位エージェント（Conductor/Section Leader）がタスクを下位エージェント（Musician）に委譲するためのスキル。
階層違反を防ぎ、正しい委譲パターンを強制する。
</description>

<triggers>
- "delegate"
- "委譲"
- "サブエージェントに任せて"
- "Musicianに実行させて"
</triggers>

<usage>
/delegate <タスク内容>
/delegate --to section_leader <タスク内容>
/delegate --parallel <タスク1> | <タスク2> | <タスク3>
</usage>

## 実行手順

### 1. 階層の確認

現在のエージェントの役割を確認:

- **Conductor**: Section Leader または Musician に委譲可能
- **Section Leader**: Musician にのみ委譲可能
- **Musician**: 委譲不可（自分で実行）

### 2. 委譲先の決定

| 委譲元 | 委譲先 | 用途 |
|--------|--------|------|
| Conductor | Section Leader | 複雑なタスク（さらに分解が必要） |
| Conductor | Musician | 単純なタスク（直接実行可能） |
| Section Leader | Musician | すべてのタスク |

### 3. サブエージェントの起動

Task ツールを使用:

```
Task tool parameters:
- subagent_type: "general-purpose"
- model: "sonnet"  # Musician は sonnet を使用
- prompt: |
    ## Hierarchy Context
    Parent: {current_role}
    Role: musician

    ## Permissions Granted
    - Read all files
    - Write/Edit files
    - Safe bash commands (git, jj, npm, pytest, ruff)

    ## Persona
    Senior Software Engineer として作業してください。

    ## Task
    {タスク内容}

    ## Output Format
    完了後、以下の形式で報告:
    - status: done / failed / blocked
    - summary: 結果の要約
    - files_modified: 変更したファイル一覧
```

### 4. 並列委譲（--parallel）

複数タスクを並列実行する場合:

```
Task tool (1つ目):
- run_in_background: true
- prompt: "タスク1..."

Task tool (2つ目):
- run_in_background: true
- prompt: "タスク2..."

Task tool (3つ目):
- run_in_background: true
- prompt: "タスク3..."
```

## 禁止事項

### 絶対にやってはいけないこと

1. **Conductor/Section Leader が直接 Edit/Write を使う**
   - → 必ず Musician に委譲

2. **Conductor が Musician に直接指示**
   - → Section Leader を経由（複雑なタスクの場合）

3. **Musician がサブエージェントを spawn**
   - → Musician は最下層、自分で実行

## 例

### 例1: 単純なファイル編集

```
/delegate README.md に新しいセクションを追加して
```

→ Musician を spawn して編集を委譲

### 例2: 複雑な機能実装

```
/delegate --to section_leader 認証システムを実装して
```

→ Section Leader を spawn
→ Section Leader が複数の Musician に分解して並列実行

### 例3: 並列テスト実行

```
/delegate --parallel ユニットテスト | 統合テスト | E2Eテスト
```

→ 3つの Musician を並列 spawn

## エラーハンドリング

### 階層違反が検出された場合

`enforce-hierarchy.py` フックがブロック:

```
⛔ 階層違反: Conductor（指揮者）は直接ファイルを編集できません。
→ /delegate を使用してください
```

### Musician が委譲しようとした場合

```
⛔ Musician は委譲できません。自分でタスクを実行してください。
```

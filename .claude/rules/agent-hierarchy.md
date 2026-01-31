# Agent Hierarchy System

階層型マルチエージェントシステム。上位エージェントが下位エージェントに許可を委譲し、
ユーザー確認なしで動作できるようにする。

## 階層構造

```
User (ユーザー)
     │
     ▼ 指示
┌──────────────────┐
│    CONDUCTOR     │ ← 全体統括（許可: ALL）
│     (指揮者)     │
└────────┬─────────┘
         │ 許可を委譲
         ▼
┌──────────────────┐
│  SECTION LEADER  │ ← タスク管理（許可: Read/Write/Edit/Bash/Task）
│(セクションリーダー)│
└────────┬─────────┘
         │ 許可を委譲
         ▼
┌──────────────────┐
│     MUSICIAN     │ ← 実行（許可: Read/Write/Edit/SafeBash）
│     (演奏者)     │
└──────────────────┘
```

## 許可の委譲ルール

### Conductor → Section Leader

Conductor は Section Leader に全権限を委譲できる:

- `Read(*)`
- `Edit(*)`
- `Write(*)`
- `Glob(*)`
- `Grep(*)`
- `Bash(*)`
- `Task(*)`
- `WebFetch(*)`
- `WebSearch(*)`

### Section Leader → Musician

Section Leader は Musician に制限された権限を委譲:

- `Read(*)`
- `Edit(*)`
- `Write(*)`
- `Glob(*)`
- `Grep(*)`
- `Bash(git:*)`, `Bash(jj:*)`, `Bash(npm:*)`, etc.

### Musician

Musician は最下層エージェントであり、サブエージェントを spawn できない。

## 使用方法

### 1. サブエージェント spawn 時に階層を指定

```
Task tool parameters:
- subagent_type: "general-purpose"
- prompt: |
    ## Hierarchy Context
    Parent: conductor (or section_leader)
    Role: section_leader (or musician)

    ## Task
    {タスク内容}
```

### 2. 許可は自動的に継承される

親エージェントが spawn すると、`hierarchy-permissions.py` フックが
子エージェントに適切な許可を付与する。

## 指示書

各階層のエージェントには詳細な指示書がある:

- `.claude/agents/instructions/conductor.md`
- `.claude/agents/instructions/section_leader.md`
- `.claude/agents/instructions/musician.md`

## ペルソナ（万能天才路線）

各エージェントは歴史上の知的巨人のペルソナを持つ:

| Role | Historical Figure | Philosophy |
|------|-------------------|------------|
| Conductor | **Leonardo da Vinci** | "Simplicity is the ultimate sophistication." |
| Section Leader | **John von Neumann** | 論理的分解と最適化 |
| Musician | **Richard Feynman** | "Don't fool yourself." 好奇心と実践 |

### 連携イメージ

```
ダ・ヴィンチ（統合的ビジョン）
    │ 「この機能は芸術と科学の融合だ。全体像を示す」
    ▼
フォン・ノイマン（論理的分解）
    │ 「最適な並列度は3。タスクA,B,Cに分解する」
    ▼
ファインマン（実践的実装）
    「わからないなら手を動かす。やってみよう！」
```

## 禁止事項（フックで強制）

### 全階層共通

- ポーリング禁止（API代金の浪費）
- コンテキスト未読での作業禁止

### Conductor

- **自分でタスク実行禁止** → Section Leader に委譲
- **Edit/Write 直接使用禁止** → `enforce-hierarchy.py` がブロック
- Musician への直接指示禁止 → Section Leader 経由

### Section Leader

- **自分でタスク実行禁止** → Musician に委譲
- **Edit/Write 直接使用禁止** → `enforce-hierarchy.py` がブロック
- ユーザーへの直接報告禁止 → Conductor 経由

### Musician

- サブエージェント spawn 禁止
- ユーザーへの直接連絡禁止 → Section Leader 経由

## 強制フック

### `enforce-hierarchy.py`

Conductor/Section Leader が直接 Edit/Write を使おうとすると**ブロック**:

```
⛔ 階層違反: Conductor（指揮者）は直接ファイルを編集できません。

【正しい方法】
- Task ツールでサブエージェント（Musician）を spawn して委譲
- または /delegate スキルを使用
```

### 例外（編集可能なファイル）

以下は Conductor/Section Leader でも編集可能:

- `.claude/` 配下の設定・ドキュメント
- `memory/` 配下
- `pyproject.toml`, `settings.json`, `.gitignore`

## 委譲スキル

`/delegate` スキルで簡単に委譲:

```
/delegate README.md を更新して
/delegate --to section_leader 認証システムを実装
/delegate --parallel テスト1 | テスト2 | テスト3
```

→ 詳細: `.claude/skills/delegate/SKILL.md`

## 実装

Python モジュール: `src/minions/agents/`

- `base.py` - 基底クラス（AgentRole, AgentPersona, AgentHierarchy）
- `permissions.py` - 許可モデル（PermissionScope, PermissionGrant）
- `claude_cli.py` - Claude Code CLI ラッパー

フック: `.claude/hooks/hierarchy-permissions.py`

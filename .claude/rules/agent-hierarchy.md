# Agent Hierarchy System (2-Tier)

2層階層型マルチエージェントシステム。Conductor が Musician に委譲して作業を進める。

## 階層構造

```
User (ユーザー)
     │
     ▼ 指示
┌──────────────────────────────────┐
│   CONDUCTOR: Leonardo da Vinci   │ ← 統合的ビジョン（指揮・計画）
│   "Simplicity is the ultimate    │
│    sophistication."              │
└────────────┬─────────────────────┘
             │ 許可を委譲
             ▼
┌──────────────────────────────────┐
│   MUSICIAN: Richard Feynman      │ ← 実行（手を動かす）
│   "Don't fool yourself."         │
│   好奇心と実践                    │
└──────────────────────────────────┘
```

**Note**: Section Leader（John von Neumann）は将来の拡張オプション。現在は2層で運用。

## 許可の委譲ルール

### Conductor → Musician

Conductor は Musician に全権限を委譲できる:

- `Read(*)`
- `Edit(*)`
- `Write(*)`
- `Glob(*)`
- `Grep(*)`
- `Bash(*)`
- `Task(*)`
- `WebFetch(*)`
- `WebSearch(*)`

### Musician

Musician は最下層エージェントであり、サブエージェントを spawn できない
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
    Parent: conductor
    Role: musician

    ## Task
    {タスク内容}
```

### 2. 許可は自動的に継承される

Conductor が Musician を spawn すると、適切な許可が自動的に付与される。

## 指示書

各階層のエージェントには詳細な指示書がある:

- `.claude/agents/instructions/conductor.md`
- `.claude/agents/instructions/musician.md`

**Note**: `section_leader.md` は将来の拡張用に保持

## ペルソナ（万能天才路線）

各エージェントは歴史上の知的巨人のペルソナを持つ:

| Role | Historical Figure | Philosophy |
|------|-------------------|------------|
| Conductor | **Leonardo da Vinci** | "Simplicity is the ultimate sophistication." 統合的ビジョン |
| Musician | **Richard Feynman** | "Don't fool yourself." 好奇心と実践 |

**Note**: Section Leader（John von Neumann）は将来の拡張用に保持。

### 連携イメージ（2層）

```
ダ・ヴィンチ（Conductor）
    │ 「この機能の全体像を示す。君に実装を任せる」
    ▼
ファインマン（Musician）
    「わからないなら手を動かす。やってみよう！」
```

## 禁止事項（フックで強制）

### 全階層共通

- ポーリング禁止（API代金の浪費）
- コンテキスト未読での作業禁止

### Conductor

- **過度な直接作業禁止** → `enforce-delegation.py` が警告・ブロック
  - 連続3回の作業ツール使用で警告
  - 連続5回の作業ツール使用でブロック
- 委譲すべきタスクは Musician へ Task ツールで委譲

### Musician

- サブエージェント spawn 禁止（最下層エージェント）
- 制限なし（自由に作業可能）

## 強制フック

### `enforce-delegation.py`

Conductor が委譲なしで連続作業すると警告・ブロック:

**動作:**
- 連続3回の作業ツール使用 → ⚠ 警告
- 連続5回の作業ツール使用 → ⛔ ブロック

**作業ツール**: `Edit`, `Write`, `Bash`, `WebFetch`, `WebSearch`

**リセット条件:**
- Task ツールで Musician へ委譲するとカウンターリセット
- 10分間作業なしでカウンターリセット

### 例外（編集可能なファイル）

以下は Conductor でもカウントされない（自由に編集可能）:

- `.claude/` 配下の設定・ドキュメント
- `memory/` 配下
- `pyproject.toml`, `settings.json`, `.gitignore`

## 委譲スキル

`/delegate` スキルで簡単に委譲:

```
/delegate README.md を更新して
/delegate --parallel テスト1 | テスト2 | テスト3
```

→ 詳細: `.claude/skills/delegate/SKILL.md`

**Note**: `--to section_leader` オプションは将来の拡張用

## 実装

Python モジュール: `src/minions/agents/`

- `base.py` - 基底クラス（AgentRole, AgentPersona, AgentHierarchy）
- `permissions.py` - 許可モデル（PermissionScope, PermissionGrant）
- `claude_cli.py` - Claude Code CLI ラッパー

フック: `.claude/hooks/hierarchy-permissions.py`

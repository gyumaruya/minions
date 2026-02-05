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

## ワークフロー

### 作業フロー

1. **自由な作業** - Conductor も Musician も制限なく作業可能
2. **適切な委譲** - 複雑なタスクは Musician に委譲（推奨）
3. **完了時検証** - 作業完了後に検証スクリプトを実行

### 推奨事項

#### Conductor（指揮者）

- 全体設計・計画・調整に注力
- 実装は Musician に委譲することを推奨（強制ではない）
- `.claude/` 配下の設定・ドキュメントは自由に編集可

#### Musician（演奏者）

- 実装・検証・テストを担当
- サブエージェント spawn は不要（最下層）
- すべてのツールを自由に使用可

## 検証システム

### 事後検証アプローチ

**旧システム**: 事前制限 → 作業をブロック
**新システム**: 事後検証 → 自由に作業、完了時に検証

### 検証方法

```bash
# 手動検証
./scripts/verify.sh
```

検証内容:
- Git status / diff
- Lint / Format check
- Type check
- Tests
- AI による分析（Copilot）

→ 詳細: `.claude/docs/VERIFICATION_SYSTEM.md`

### 検証タイミング

- 実装完了後
- コミット前
- PR 作成前

### 自動検証（将来実装予定）

完了時に `[[VERIFY:done]]` マーカーを含めると自動検証:

```
実装完了しました [[VERIFY:done]]
```

## 委譲スキル

`/delegate` スキルで簡単に委譲:

```
/delegate README.md を更新して
/delegate --parallel テスト1 | テスト2 | テスト3
```

→ 詳細: `.claude/skills/delegate/SKILL.md`

**Note**: `--to section_leader` オプションは将来の拡張用

## 実装

検証スクリプト: `scripts/verify.sh`

Python モジュール: `src/minions/agents/`（階層管理用）

- `base.py` - 基底クラス（AgentRole, AgentPersona, AgentHierarchy）
- `permissions.py` - 許可モデル（PermissionScope, PermissionGrant）
- `claude_cli.py` - Claude Code CLI ラッパー

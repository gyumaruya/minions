# Minions

**黄色い精霊たちがあなたの開発を加速する**

```
        ╭──────────────────────────────────────╮
        │   "Bee-do! Bee-do!"                  │
        │                                      │
        │      ╭─────╮   ╭─────╮   ╭─────╮     │
        │      │ ◉ ◉ │   │ ◉ ◉ │   │ ◉ ◉ │     │
        │      │  ▽  │   │  ▽  │   │  ▽  │     │
        │      ╰─────╯   ╰─────╯   ╰─────╯     │
        │     Codex     Gemini    Copilot      │
        │                                      │
        │   Claude Code が指揮する精霊たち     │
        ╰──────────────────────────────────────╯
```

AI エージェントたちを「召喚」し、協調させる開発フレームワーク。
**記憶と改善ループ**を Hooks で強制し、使うほど賢くなる自己改善システム。

---

## Why Minions?

| 課題 | Minions の解決策 |
|------|------------------|
| Claude Code 単体では深い推論が苦手 | **Codex** を召喚して設計相談 |
| 大規模コードベースの理解が難しい | **Gemini** (1M tokens) で全体分析 |
| コストが心配 | **Copilot** (Sonnet 無料枠) をデフォルトに |
| 学習が蓄積しない | **Memory Layer** で自己改善 |
| 口約束で守られない | **Hooks** でワークフローを強制 |

---

## Concept

### 1. Multi-Agent Orchestration

Claude Code を**指揮者**として、専門家エージェントを召喚:

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code (Conductor)                   │
│                    Leonardo da Vinci の視点で統括            │
│                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│   │   Codex    │  │   Gemini   │  │  Copilot   │         │
│   │  深い推論   │  │  リサーチ   │  │ コスト効率  │         │
│   │  設計判断   │  │  1M tokens │  │  デフォルト │         │
│   └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 2. Hierarchical Agents with Personas

歴史上の天才たちをペルソナとして採用:

| Role | Persona | Philosophy |
|------|---------|------------|
| **Conductor** | Leonardo da Vinci | "Simplicity is the ultimate sophistication." |
| **Musician** | Richard Feynman | "Don't fool yourself." |

**Conductor** (da Vinci) が全体を俯瞰し、**Musician** (Feynman) が手を動かして実装する。

### 3. Self-Improving Memory

使うほど賢くなる記憶システム:

```
セッション開始
    ↓
[Hook] load-memories.py → 過去の記憶を自動注入
    ↓
ユーザー: 「PRは日本語にして」
    ↓
[Hook] auto-learn.py → パターンを自動検出・記憶
    ↓
次回セッションで自動反映
```

### 4. Hook-Enforced Workflows

「やろう」ではなく「やらざるを得ない」仕組み:

```
❌ Prompt だけ: 「PRは日本語で書いてね」→ 忘れる
✅ Hook 強制:   enforce-japanese.py が英語PRをブロック
```

---

## Inspirations

Minions は以下のプロジェクトから着想を得ています:

| Project | Contribution |
|---------|--------------|
| [claude-code-orchestra](https://github.com/DeL-TaiseiOzaki/claude-code-orchestra) | ベースアーキテクチャ、エージェント協調パターン |
| [multi-agent-shogun](https://github.com/y-i-labs/multi-agent-shogun) | 階層型エージェント、歴史的ペルソナの採用 |
| [mem0](https://github.com/mem0ai/mem0) | 記憶レイヤー、セマンティック検索、自己改善ループ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User (ユーザー)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONDUCTOR (Claude Code)                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Hooks Layer                           │   │
│  │  • load-memories.py    - 記憶を注入                      │   │
│  │  • auto-learn.py       - 学習パターン検出                │   │
│  │  • agent-router.py     - 適切なエージェントへルーティング │   │
│  │  • enforce-*.py        - ワークフロー強制                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Memory Broker                         │   │
│  │  JSONL (真実の源泉) ←→ mem0 (セマンティック検索)          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │    Codex     │  │    Gemini    │  │   Copilot    │       │
│  │   gpt-5.2    │  │  gemini-3-pro │  │  sonnet-4    │       │
│  │   設計・推論  │  │   リサーチ    │  │  デフォルト   │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      MUSICIAN                            │   │
│  │                (Subagent - Richard Feynman)              │   │
│  │                   実装・検証・報告                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

```bash
# Claude Code
npm install -g @anthropic-ai/claude-code
claude login

# Codex CLI
npm install -g @openai/codex
codex login

# Gemini CLI
npm install -g @google/gemini-cli
gemini login

# Copilot CLI (オプション)
npm install -g @anthropic-ai/claude-code  # claude の alias として copilot を使用
```

### Installation

既存プロジェクトに導入:

```bash
git clone --depth 1 https://github.com/gyumaruya/minions.git .minions-starter
cp -r .minions-starter/.claude .minions-starter/.codex .minions-starter/.gemini .minions-starter/CLAUDE.md .
rm -rf .minions-starter

# Python 依存関係（Memory Layer 用）
uv sync
```

### Start

```bash
claude
```

セッション開始時に自動で:
1. 過去の記憶をコンテキストに注入
2. Draft PR を自動作成
3. エージェントルーティングを有効化

---

## Key Features

### Agent Selection (自動)

```
ユーザー: 「どう設計すべき？」
    ↓
[Hook] agent-router.py
    ↓
→ Codex を推奨（設計タスク検出）

ユーザー: 「調べて」
    ↓
→ Gemini を推奨（リサーチタスク検出）

ユーザー: 「この関数を直して」
    ↓
→ Copilot を推奨（一般タスク）
```

### Memory System (自動学習)

```bash
# 自動学習（Hook による検出）
ユーザー: 「PRは日本語にして」
→ preference として自動記憶

# 手動記憶
/remember PRは日本語で書く

# 検索
/remember search 日本語

# CLI
uv run python -m minions.memory.cli list
```

### Hook-Enforced Rules

| Hook | 強制内容 |
|------|----------|
| `enforce-japanese.py` | PR/コミットは日本語必須 |
| `enforce-draft-pr.py` | PR は必ず Draft で作成 |
| `enforce-no-merge.py` | エージェントによるマージ禁止 |
| `enforce-delegation.py` | Conductor は委譲を強制 |
| `prevent-secrets-commit.py` | シークレットのコミットブロック |

---

## Hooks (ワークフロー強制)

### Memory Hooks

| Hook | Timing | 機能 |
|------|--------|------|
| `load-memories.py` | セッション開始 | 過去の記憶をコンテキストに注入 |
| `auto-learn.py` | プロンプト送信時 | ユーザー修正パターンを自動学習 |

### Agent Hooks

| Hook | Timing | 機能 |
|------|--------|------|
| `agent-router.py` | プロンプト送信時 | 適切なエージェントを推奨 |
| `hierarchy-permissions.py` | サブエージェント spawn 時 | 許可を自動委譲 |
| `enforce-delegation.py` | ツール使用時 | Conductor の過度な直接作業をブロック |

### Quality Hooks

| Hook | Timing | 機能 |
|------|--------|------|
| `lint-on-save.py` | ファイル保存後 | 自動 lint 実行 |
| `check-codex-before-write.py` | ファイル書き込み前 | Codex 相談を提案 |
| `post-test-analysis.py` | テスト実行後 | 失敗分析・改善提案 |

### Git Hooks

| Hook | Timing | 機能 |
|------|--------|------|
| `auto-create-pr.py` | セッション開始 | Draft PR 自動作成 |
| `enforce-draft-pr.py` | PR 作成時 | Draft 強制 |
| `enforce-no-merge.py` | マージ操作時 | マージをブロック |
| `enforce-japanese.py` | コミット/PR 時 | 日本語強制 |

---

## Skills (再利用可能なワークフロー)

```bash
/startproject <機能名>   # マルチエージェント協調でプロジェクト開始
/plan <タスク>           # 実装計画を作成
/tdd <機能>              # テスト駆動開発
/remember <内容>         # 記憶を保存
/delegate <タスク>       # Musician に委譲
/checkpointing           # セッション状態を保存
```

---

## Memory Layer

### 3-Layer Memory

| Layer | Scope | 永続性 | 用途 |
|-------|-------|--------|------|
| **Session** | セッション内 | 一時的 | 作業コンテキスト |
| **User** | ユーザー全体 | 永続 | 好み、ワークフロー |
| **Public** | エージェント間 | 永続 | 設計決定、リサーチ |

### Memory Types

| Type | 用途 | 自動学習 |
|------|------|---------|
| `preference` | ユーザーの好み | ✓「〜にして」 |
| `workflow` | ワークフロー | ✓「いつも〜」 |
| `decision` | 設計判断 | - |
| `error` | エラーパターン | ✓ 解決時 |
| `research` | リサーチ結果 | - |

### Storage

```
.claude/memory/
├── events.jsonl              # メイン記憶 (JSONL)
├── sessions/                 # セッション別記憶
└── qdrant/                   # mem0 ベクトル DB
```

---

## Development

### Tech Stack

| Tool | Purpose |
|------|---------|
| **git** | バージョン管理（main 直接プッシュ禁止） |
| **uv** | パッケージ管理（pip 禁止） |
| **ruff** | Lint / Format |
| **ty** | 型チェック |
| **pytest** | テスト |

### Commands

```bash
# 品質チェック
poe lint        # ruff check + format
poe typecheck   # ty check
poe test        # pytest
poe all         # 全チェック

# Memory CLI
uv run python -m minions.memory.cli list
uv run python -m minions.memory.cli search "keyword"
```

---

## Vision

Minions が目指す姿:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🎯 Self-Improving AI Development Environment                  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  1. 記憶する   │ 過去の学びを蓄積、同じミスを繰り返さない │   │
│   │  2. 改善する   │ パターンを検出し、自動でルール化        │   │
│   │  3. 強制する   │ Hooks で「忘れない」を実現              │   │
│   │  4. 協調する   │ 適材適所でエージェントを召喚           │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   使えば使うほど、あなた専用の開発環境に進化する               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Contributing

Issues & PRs welcome!

```bash
# 開発環境セットアップ
git clone https://github.com/gyumaruya/minions.git
cd minions
uv sync --all-extras
```

---

## License

MIT

---

*"Banana!" - The Minions*

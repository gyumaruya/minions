# Minions

**黄色い精霊たちがあなたの開発を加速する**

```
        ╭────────────────────────────────────────────╮
        │   "Bee-do! Bee-do!"                        │
        │                                            │
        │      ╭─────╮   ╭─────╮   ╭─────╮          │
        │      │ ◉ ◉ │   │ ◉ ◉ │   │ ◉ ◉ │          │
        │      │  ▽  │   │  ▽  │   │  ▽  │          │
        │      ╰─────╯   ╰─────╯   ╰─────╯          │
        │     Codex     Gemini    Copilot           │
        │                                            │
        │   Orchestrated by Claude Code              │
        ╰────────────────────────────────────────────╯
```

AI エージェントたちを「召喚」し、協調させる開発フレームワーク。
**記憶と改善ループ**を Hooks で強制し、使うほど賢くなる自己改善システム。

**設計哲学:**
- **軽量**: 最小限のオーバーヘッド、ツールの進化を妨げない
- **フック**: 行動を強制、口約束で終わらせない
- **記憶**: 学習を蓄積、繰り返さない

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

## Design Philosophy

### 軽量・ツール非依存

**各種 AI CLI の進化を妨げない設計:**

```
Claude Code, Codex, Gemini, Copilot
         │
         ▼
┌────────────────────────┐
│  Minions (thin layer)  │  ← 軽量なアダプター
│  • Hooks (強制)        │
│  • Memory (蓄積)       │
└────────────────────────┘
         │
         ▼
   Your Project
```

**ポイント:**
- ツール本体には手を加えない
- 薄い層（フック + 記憶）のみを提供
- ツールが更新されても影響を受けない
- 新しいツールが出ても簡単に統合

### フックがキモ

**「やろう」ではなく「やらざるを得ない」:**

| 従来のアプローチ | Minions のアプローチ |
|--------------|------------------|
| Prompt: "Use Japanese for PR" | Hook: English PR をブロック |
| Prompt: "Always consult Codex" | Hook: 設計時に Codex を提案 |
| Prompt: "Remember this" | Hook: パターンを自動学習 |

**結果:** 口約束で終わらず、確実に実行される

### 記憶がキモ

**使うほど賢くなる:**

```
Day 1: "Use Japanese for PR"
  → Memorized

Day 2:
  → Auto-applied (no reminder needed)

Day 30:
  → 30 learned preferences, 50 workflows
  → Personalized development environment
```

**XDG準拠のグローバル記憶:**
- `~/.config/ai/memory/events.jsonl` - 全プロジェクト共通
- 一度学習した好みが全体に適用
- プロジェクト固有の記憶も分離可能（Phase 2）

---

## Concept

### 1. Multi-Agent Orchestration

Claude Code を**指揮者**として、専門家エージェントを召喚:

```
┌─────────────────────────────────────────────────────────┐
│              Claude Code (Conductor)                    │
│              Leonardo da Vinci's Vision                 │
│                                                         │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │   Codex     │  │   Gemini    │  │  Copilot    │    │
│   │  Reasoning  │  │  Research   │  │  Default    │    │
│   │  Design     │  │  1M tokens  │  │  Cost-Eff   │    │
│   └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────┘
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
Session Start
    ↓
[Hook] load-memories.py → Auto-inject past memories
    ↓
User: "Use Japanese for PR"
    ↓
[Hook] auto-learn.py → Detect & record pattern
    ↓
Auto-applied in next session
```

### 4. Hook-Enforced Workflows

「やろう」ではなく「やらざるを得ない」仕組み:

```
❌ Prompt only: "Use Japanese for PR" → Forgotten
Hook enforced: enforce-japanese.py blocks English PR
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
│                            User                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONDUCTOR (Claude Code)                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Hooks Layer                           │   │
│  │  • load-memories.py    - Inject memories                 │   │
│  │  • auto-learn.py       - Detect learning patterns        │   │
│  │  • agent-router.py     - Route to appropriate agent      │   │
│  │  • enforce-*.py        - Enforce workflows               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Memory Broker                         │   │
│  │  JSONL (Source of Truth) <-> mem0 (Semantic Search)     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │    Codex     │  │    Gemini    │  │   Copilot    │       │
│  │   gpt-5.2    │  │  gemini-3-pro │  │  sonnet-4    │       │
│  │ Design/Logic │  │   Research   │  │   Default    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      MUSICIAN                            │   │
│  │                (Subagent - Richard Feynman)              │   │
│  │              Implementation / Verification               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Global Setup (Phase 1)

**新プロジェクトでも即座に使える:**

### セットアップ（初回のみ）

```bash
# 1. minions をクローン
git clone https://github.com/gyumaruya/minions.git ~/minions
cd ~/minions

# 2. Rust フックをビルド
cd resources/hooks-rs && cargo build --release && cd ../..

# 3. グローバル設定をセットアップ
bash scripts/setup-global-config.sh
```

**セットアップスクリプトの実行内容:**

1. `~/.config/ai/` と `~/.claude/` ディレクトリを作成
2. フックバイナリへのシンボリックリンク作成
3. スキル、エージェント、ルールへのシンボリックリンク作成
4. CLAUDE.md へのシンボリックリンク作成
5. グローバル記憶の初期化
6. `~/.claude/settings.json` にフック定義を設定

**これで完了！** 以降、すべてのプロジェクトで：
- **フック（23個）**: セキュリティ、ワークフロー、記憶
- **スキル（18個）**: `/startproject`, `/delegate`, `/checkpointing` など
- **エージェント階層**: Conductor → Musician
- **ルール（10ファイル）**: 言語、開発環境、セキュリティなど
- **記憶システム**: 自動学習と改善ループ

### グローバル構成

```
~/.config/ai/              # ツール非依存（XDG準拠）
├── hooks/
│   └── bin/              # フックバイナリ (symlink)
└── memory/
    └── events.jsonl      # グローバル記憶

~/.claude/                 # Claude Code が自動認識
├── skills/               # スキル (symlink)
├── agents/               # エージェント設定 (symlink)
├── rules/                # ルール (symlink)
├── CLAUDE.md             # プロジェクト指示書 (symlink)
└── settings.json         # 全23フック定義
```

**配置場所の方針:**
- **`~/.config/ai/`**: フック・記憶（ツール非依存、将来的に他のAIツールとも共有可能）
- **`~/.claude/`**: スキル・エージェント・ルール・CLAUDE.md（Claude Code が自動認識）

**利点:**
- 新プロジェクト = 設定ゼロ
- 学習した好み = 全体に適用
- シンボリックリンク = minions で更新すれば即座に反映
- ツール更新 = 影響なし（疎結合）

### 動作確認

```bash
# グローバル設定を確認
ls -la ~/.config/ai/
ls -la ~/.claude/

# スキルが使えることを確認
ls ~/.claude/skills/

# CLAUDE.md が読めることを確認
head -5 ~/.claude/CLAUDE.md
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

### 新規プロジェクトで使う

グローバルセットアップ完了後、新規プロジェクトでは**何も設定不要**です。

```bash
# 任意のプロジェクトで Claude Code を起動
cd ~/your-project
claude
```

セッション開始時に自動で:
1. 過去の記憶をコンテキストに注入
2. Draft PR を自動作成
3. 全23フックが有効化
4. 全18スキルが使用可能
5. エージェント階層が利用可能

---

## Key Features

### Agent Selection (自動)

```
User: "How should I design this?"
    ↓
[Hook] agent-router.py
    ↓
→ Recommend Codex (design task detected)

User: "Research this"
    ↓
→ Recommend Gemini (research task detected)

User: "Fix this function"
    ↓
→ Recommend Copilot (general task)
```

### Memory System (自動学習)

```bash
# Auto-learning (detected by Hook)
User: "Use Japanese for PR"
→ Auto-memorized as preference

# Manual memory
/remember Use Japanese for PRs

# Search
/remember search Japanese

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

# Shell script tests (bats-core)
bats tests/setup-global-config.bats  # セットアップスクリプトのテスト
```

### Testing

#### Python Tests (pytest)

```bash
# 全テスト実行
uv run pytest -v

# 特定のテストファイルのみ
uv run pytest tests/test_memory.py -v

# カバレッジ付き
uv run pytest --cov=src --cov-report=term-missing
```

#### Shell Script Tests (bats-core)

```bash
# bats-core のインストール（初回のみ）
brew install bats-core

# セットアップスクリプトのテスト
bats tests/setup-global-config.bats

# 詳細出力
bats --print-output-on-failure tests/setup-global-config.bats
```

テストカバレッジ:
- ディレクトリ構造の作成
- シンボリックリンクの作成と再作成
- 記憶ファイルの移行
- 設定ファイルの作成とバックアップ
- エラーケース（ディレクトリ不在、バイナリ不在）
- 複数回実行時の安全性

---

## Vision

Minions が目指す姿:

**Minions Vision:**

| Stage | Description |
|-------|-------------|
| **1. Remember** | Accumulate past learnings, avoid repeating mistakes |
| **2. Improve** | Detect patterns, auto-convert to rules |
| **3. Enforce** | Hooks ensure "never forget" |
| **4. Collaborate** | Summon the right agent for the right task |

**The more you use it, the more it evolves into your personalized development environment.**

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

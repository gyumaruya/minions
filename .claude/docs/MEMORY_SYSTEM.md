# 記憶レイヤーと自己改善システム

Claude Code Orchestra の記憶・学習・自己改善の仕組みを解説する。

---

## アーキテクチャ概要

**ハイブリッド方式**: JSONL（真実の源泉）+ mem0（ベクトル索引）

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Broker                               │
│         スキーマ統一・アクセス制御・機密除去・要約                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  書き込みフロー:                                                 │
│  Agent → validate → redact → persist JSONL → index mem0        │
│                                                                 │
│  読み取りフロー:                                                 │
│  query → scope filter → keyword + semantic → rerank → Agent    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   JSONL     │───▶│   mem0      │◀───│   Agents    │         │
│  │ (真実の源泉) │    │ (意味検索)   │    │ Claude/Codex│         │
│  │ 監査・再構築 │    │ ベクトル索引 │    │ Gemini/etc  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
│  events.jsonl                                                   │
│  sessions/{id}.jsonl                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## メモリスコープ（3層）

| Layer | Scope | 永続性 | ファイル | 用途 |
|-------|-------|--------|---------|------|
| **Session** | セッション内 | 一時的 | `sessions/{id}.jsonl` | 作業コンテキスト |
| **User** | ユーザー全体 | 永続 | `events.jsonl` | 好み、ワークフロー |
| **Agent/Public** | エージェント間 | 永続 | `events.jsonl` | 設計決定、リサーチ |

---

## 統一スキーマ

```python
@dataclass
class MemoryEvent:
    # 必須
    content: str              # 記憶内容
    memory_type: MemoryType   # observation/decision/plan/preference/...
    scope: MemoryScope        # session/user/agent/public
    source_agent: AgentType   # claude/codex/gemini/copilot

    # 自動生成
    id: str                   # 一意ID
    created_at: str           # ISO timestamp

    # オプション
    context: str = ""         # 追加コンテキスト
    confidence: float = 1.0   # 確度 (0-1)
    ttl_days: int | None      # 有効期限
    tags: list[str] = []      # タグ
    metadata: dict = {}       # メタデータ
```

### MemoryType（記憶タイプ）

| Type | 用途 | 例 |
|------|------|-----|
| `observation` | 事実の観察 | 「このファイルは認証を担当」 |
| `decision` | 設計判断 | 「JWTを使用」 |
| `plan` | 計画・意図 | 「次はテストを書く」 |
| `preference` | ユーザー好み | 「日本語で書く」 |
| `workflow` | ワークフロー | 「自動でPR作成」 |
| `error` | エラーパターン | 「メール→noreply」 |
| `research` | リサーチ結果 | 「FastAPIが高速」 |

### MemoryScope（スコープ）

| Scope | 可視性 | 用途 |
|-------|--------|------|
| `session` | セッション内のみ | 一時的な作業メモ |
| `user` | ユーザー全体 | 永続的な好み・習慣 |
| `agent` | 特定エージェント | エージェント固有の知識 |
| `public` | 全エージェント共有 | 設計決定、リサーチ |

---

## 使い方

### 基本操作

```python
from minions.memory import MemoryBroker, MemoryType, MemoryScope, AgentType

# Broker取得（グローバルシングルトン）
from minions.memory import get_broker
broker = get_broker()

# または新規作成
broker = MemoryBroker(
    base_dir=Path("~/.minions/.claude/memory"),
    enable_mem0=True,  # セマンティック検索を有効化
)

# 記憶を追加
event = broker.add(
    content="PRは日本語で書く",
    memory_type=MemoryType.PREFERENCE,
    scope=MemoryScope.USER,
    source_agent=AgentType.CLAUDE,
    context="ユーザーからの指示",
)

# 検索（キーワード + セマンティック）
results = broker.search(
    query="日本語",
    scope=MemoryScope.USER,
    limit=10,
)
```

### 便利メソッド

```python
# ユーザー好みを記録
broker.remember_preference("Dark mode preferred")

# 設計決定を記録（Codex由来）
broker.remember_decision("Use JWT for auth", context="auth設計")

# リサーチ結果を記録（Gemini由来）
broker.remember_research("FastAPI is performant", topic="frameworks")

# エラーパターンを記録
broker.remember_error(
    error="jj describe でメールエラー",
    solution="noreply メールを使用"
)

# ワークフローを記録
broker.remember_workflow(
    "コミット後は自動でPR作成",
    trigger="コミット完了時"
)
```

### 統計情報

```python
stats = broker.get_stats()
# {
#   "total_events": 42,
#   "session_events": 5,
#   "session_count": 3,
#   "by_type": {"preference": 10, "decision": 15, ...},
#   "by_agent": {"claude": 20, "codex": 12, ...},
#   "by_scope": {"user": 30, "public": 12},
#   "mem0_enabled": True
# }
```

---

## 埋め込みプロバイダ

### サポートプロバイダ

| Provider | 要件 | メリット | デメリット |
|----------|------|---------|-----------|
| **OpenAI** | `OPENAI_API_KEY` | 高品質 | コスト、API依存 |
| **HuggingFace** | なし（ローカル） | 無料、オフライン | 初回ダウンロード |
| **Ollama** | Ollama起動 | ローカル、高速 | セットアップ必要 |

### 自動選択

```python
from minions.memory import get_mem0_config

# 環境変数に基づいて自動設定
config = get_mem0_config(
    embedding_provider="auto",  # OPENAI_API_KEY あれば OpenAI、なければ HuggingFace
    llm_provider="auto",        # ANTHROPIC_API_KEY あれば Claude
)

broker = MemoryBroker(enable_mem0=True, mem0_config=config)
```

### 手動設定

```python
config = {
    "llm": {
        "provider": "anthropic",
        "config": {"model": "claude-sonnet-4-20250514"}
    },
    "embedder": {
        "provider": "huggingface",
        "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {"path": "~/.minions/.claude/memory/qdrant"}
    }
}
```

---

## 自動学習システム

### 動作フロー

```
セッション開始
    ↓
load-memories.py → 過去の記憶をコンテキストに注入
    ↓
ユーザー入力「PRは日本語にして」
    ↓
auto-learn.py → パターン検出 → 記憶に自動保存
    ↓
次回セッションで反映
```

### 自動学習トリガー（実装済み）

| パターン | 例 | 記憶タイプ |
|---------|-----|-----------|
| `〜にして` | 「PRは日本語にして」 | preference |
| `〜に変えて` | 「コミットメッセージに変えて」 | preference |
| `〜は違う` | 「それは違う」 | preference |
| `〜より〜がいい` | 「AよりBがいい」 | preference |
| `いつも〜` | 「いつもテスト先に書く」 | workflow |
| `毎回〜` | 「毎回レビューする」 | workflow |
| `覚えて:〜` | 「覚えて: JWTを使う」 | preference |

### Hooks（実装済み）

| Hook | 機能 | タイミング |
|------|------|-----------|
| `load-memories.py` | 記憶をコンテキストに注入 | セッション開始時 |
| `auto-learn.py` | ユーザー入力から自動学習 | 各プロンプト送信時 |
| `enforce-japanese.py` | PR/コミットの日本語強制 | Bash実行前 |
| `ensure-noreply-email.py` | noreplyメール強制 | Bash実行前 |

---

## 自己改善の適用レベル

記憶から改善への変換は3段階:

### Level 1: Hooks（自動強制）

**特徴**: ユーザー操作なしで自動実行

| Hook | 機能 |
|------|------|
| `auto-learn.py` | ユーザー修正を自動記憶 |
| `load-memories.py` | セッション開始時に記憶読み込み |
| `enforce-japanese.py` | PR/コミットの日本語強制 |
| `ensure-noreply-email.py` | noreplyメール強制 |

### Level 2: CLI / Skills（手動操作）

**特徴**: ユーザーが明示的に呼び出し

| ツール | 機能 |
|-------|------|
| `memory add` | 記憶を手動追加 |
| `memory search` | 記憶を検索 |
| `memory list` | 記憶一覧 |
| `/remember` | 記憶の保存・検索 |

### Level 3: Prompts（ガイドライン）

**特徴**: CLAUDE.md/rulesでガイド

---

## Memory CLI

コマンドラインから記憶を操作:

```bash
# 記憶を追加
uv run python -m minions.memory.cli add "PRは日本語で書く" --type preference

# 検索
uv run python -m minions.memory.cli search "日本語"

# 一覧表示
uv run python -m minions.memory.cli list --limit 10

# 統計情報
uv run python -m minions.memory.cli stats

# セッション開始時に読み込む記憶を確認
uv run python -m minions.memory.cli relevant

# JSON出力
uv run python -m minions.memory.cli --json search "日本語"

# mem0セマンティック検索を有効化
uv run python -m minions.memory.cli --mem0 search "日本語"
```

### コマンド一覧

| コマンド | 説明 |
|---------|------|
| `add <content>` | 記憶を追加 |
| `search <query>` | キーワード検索 |
| `list` | 最近の記憶一覧 |
| `stats` | 統計情報 |
| `relevant` | セッション用の関連記憶 |

### オプション

| オプション | 説明 |
|-----------|------|
| `--type`, `-t` | 記憶タイプ (preference/workflow/error/decision) |
| `--scope`, `-s` | スコープ (user/session/public) |
| `--agent`, `-a` | エージェント (claude/codex/gemini) |
| `--context`, `-c` | コンテキスト情報 |
| `--limit`, `-l` | 結果数制限 |
| `--json` | JSON形式で出力 |
| `--mem0` | mem0セマンティック検索を有効化 |

---

## ストレージ構造

```
~/.minions/.claude/memory/
├── events.jsonl              # メイン記憶ファイル
├── sessions/                 # セッション別記憶
│   ├── 20260131180000.jsonl
│   └── 20260131190000.jsonl
└── qdrant/                   # mem0ベクトルDB（オプション）
```

---

## API リファレンス

### MemoryBroker

```python
class MemoryBroker:
    def __init__(base_dir, enable_mem0, mem0_config)
    def start_session(session_id) -> str
    def add(content, memory_type, scope, source_agent, ...) -> MemoryEvent
    def write(event: MemoryEvent) -> MemoryEvent
    def search(query, scope, source_agent, memory_type, limit) -> list[MemoryEvent]
    def remember_preference(preference, context) -> MemoryEvent
    def remember_decision(decision, agent, context) -> MemoryEvent
    def remember_research(finding, topic) -> MemoryEvent
    def remember_error(error, solution) -> MemoryEvent
    def remember_workflow(workflow, trigger) -> MemoryEvent
    def get_stats() -> dict
    def cleanup_expired() -> int
```

### Schema

```python
class MemoryType(Enum):
    OBSERVATION, DECISION, PLAN, ARTIFACT, PREFERENCE, WORKFLOW, ERROR, RESEARCH

class MemoryScope(Enum):
    SESSION, USER, AGENT, PUBLIC

class AgentType(Enum):
    CLAUDE, CODEX, GEMINI, COPILOT, SYSTEM
```

---

## セキュリティ

### 自動リダクション

以下のパターンは自動的に `[REDACTED]` に置換:

- OpenAI API Key: `sk-...`
- Anthropic API Key: `sk-ant-...`
- Google API Key: `AIza...`
- GitHub Token: `ghp_...`, `gho_...`
- パスワード/シークレットパターン

---

## 今後の拡張

1. **自動要約**: 長い記憶を自動で要約
2. **忘却ポリシー**: TTL + 利用頻度で自動整理
3. **ゴールデンメモリ**: 重要な記憶を固定
4. **クロスプロジェクト**: 複数プロジェクト間の記憶共有

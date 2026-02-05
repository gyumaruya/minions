# Claude Code Orchestra

**マルチエージェント協調フレームワーク**

Claude Code が Codex CLI（深い推論）、Gemini CLI（大規模リサーチ）、Copilot CLI（サブエージェント）を統合し、各エージェントの強みを活かして開発を加速する。

---

## Session Start (MUST READ)

**セッション開始時に必ず実行:**

1. `.claude/.pr-status` を確認し、PRの状態をユーザーに報告する
2. PRがない場合は自動作成されているはず。されていなければ手動で作成を促す

```bash
# PRステータス確認
cat .claude/.pr-status 2>/dev/null || echo "PRステータスなし"
```

---

## Why This Exists

| Agent | Strength | Use For |
|-------|----------|---------|
| **Claude Code** | オーケストレーション、ユーザー対話 | 全体統括、タスク管理 |
| **Codex CLI** | 深い推論、設計判断、デバッグ | 設計相談、エラー分析、トレードオフ評価 |
| **Gemini CLI** | 1Mトークン、マルチモーダル、Web検索 | コードベース全体分析、ライブラリ調査、PDF/動画処理 |
| **Copilot CLI** | サブエージェント、GitHub連携 | コマンド提案、GitHub操作、エージェント協調 |

**IMPORTANT**: 単体では難しいタスクも、4エージェントの協調で解決できる。

---

## Context Management (CRITICAL)

Claude Code のコンテキストは **200k トークン** だが、ツール定義等で **実質 70-100k** に縮小する。

**YOU MUST** サブエージェント経由で Codex/Gemini を呼び出す（出力が10行以上の場合）。

| 出力サイズ | 方法 | 理由 |
|-----------|------|------|
| 1-2文 | 直接呼び出しOK | オーバーヘッド不要 |
| 10行以上 | **サブエージェント経由** | メインコンテキスト保護 |
| 分析レポート | サブエージェント → ファイル保存 | 詳細は `.claude/docs/` に永続化 |

```
# MUST: サブエージェント経由（大きな出力）
Task(subagent_type="general-purpose", prompt="Codexに設計を相談し、要約を返して")

# OK: 直接呼び出し（小さな出力のみ）
Bash("codex exec ... '1文で答えて'")
```

---

## Agent Selection Strategy

**優先順位に基づいてエージェントを選択する:**

| 優先度 | Agent | 使用場面 | コスト |
|--------|-------|----------|--------|
| 1 | **Codex** | 設計・デバッグ・深い推論 | 高 |
| 2 | **Gemini** | リサーチ・大規模分析・マルチモーダル | 中 |
| 3 | **Copilot** | **それ以外すべて（デフォルト）** | 低 |

### Codex を使う時（重要タスク）

- 設計判断（「どう実装？」「どのパターン？」）
- デバッグ（「なぜ動かない？」「エラーの原因は？」）
- 比較検討（「AとBどちらがいい？」）
- セキュリティ・パフォーマンス分析

→ 詳細: `.claude/rules/codex-delegation.md`

### Gemini を使う時（専門タスク）

- リサーチ（「調べて」「最新の情報は？」）
- 大規模分析（「コードベース全体を理解して」）
- マルチモーダル（「このPDF/動画を見て」）

→ 詳細: `.claude/rules/gemini-delegation.md`

### Copilot CLI を使う時（その他すべて）

- **デフォルト選択** — Codex/Gemini に該当しないタスク
- 一般的な質問・説明
- GitHub 操作
- コスト効率重視のタスク

**必須オプション**: `--model claude-sonnet-4 --allow-all --silent`

**必須プロンプト接頭辞**:
```
サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

{actual prompt}
```

→ メインエージェント（Sonnet 4、無料枠）+ サブエージェント（Opus 4.5）の構成

→ 詳細: `.claude/rules/copilot-delegation.md`

---

## Agent Hierarchy (階層型エージェントシステム) ✓ 実装済み

**自由な作業 + 事後検証**により、エージェントが効率的に協調。

**万能天才路線**: 歴史上の知的巨人をペルソナとして採用。

### 現在の構成（2層）

```
User (ユーザー)
     │
     ▼
┌──────────────────────────────────┐
│   CONDUCTOR: Leonardo da Vinci   │ ← 統合的ビジョン
│   "Simplicity is the ultimate    │
│    sophistication."              │
└────────────┬─────────────────────┘
             │ 委譲（推奨）
             ▼
┌──────────────────────────────────┐
│   MUSICIAN: Richard Feynman      │ ← 好奇心と実践
│   "Don't fool yourself."         │
│   手を動かして理解する           │
└──────────────────────────────────┘
```

**シンプルな2層構成:**
- **Conductor** — 統合的ビジョン、タスク分解、全体調整（Leonardo da Vinci）
- **Musician** — 実装と検証、手を動かす（Richard Feynman）

**将来の拡張オプション:**
- 中間層（Section Leader / John von Neumann）を追加して3層化も可能
- 現状は2層で十分なシンプルさを保持

### ワークフロー

1. **自由な作業** - 両エージェントとも制限なく作業可能
2. **適切な委譲** - Conductor は Musician に委譲を推奨（強制ではない）
3. **完了時検証** - 作業完了後に検証スクリプトを実行

### ペルソナ（万能天才路線）

歴史上の知的巨人をペルソナとして採用:

| Role | Historical Figure | Philosophy |
|------|-------------------|------------|
| Conductor | **Leonardo da Vinci** | 統合的ビジョン、美と機能の融合 |
| Musician | **Richard Feynman** | 好奇心、実践、シンプル化 |

**拡張オプション:**
| Section Leader | **John von Neumann** | 論理的分解、最適化、並列処理（3層化時）|

### 検証システム

**旧システム**: 事前制限 → 作業をブロック
**新システム**: 事後検証 → 自由に作業、完了時に自動検証

#### Phase 1: 手動検証 ✅

```bash
./scripts/verify.sh
```

#### Phase 2: 自動検証 ✅

完了時に自然な表現で完了を伝えると AI が判定して自動実行:

```
実装が完了しました。テストも通っています。
```

AI（Claude Haiku）が完了意図を検出して自動検証

検証内容:
- Git status / diff
- Lint / Format / Type check
- Tests
- AI 分析（Copilot）

→ 詳細: `.claude/docs/VERIFICATION_SYSTEM.md`
→ 階層ルール: `.claude/rules/agent-hierarchy.md`
→ 指示書: `.claude/agents/instructions/`

---

## Workflow

```
/startproject <機能名>
```

1. Gemini がリポジトリ分析（サブエージェント経由）
2. Claude が要件ヒアリング・計画作成
3. Codex が計画レビュー（サブエージェント経由）
4. Claude がタスクリスト作成
5. **別セッションで実装後レビュー**（推奨）

→ 詳細: `/startproject`, `/plan`, `/tdd` skills

---

## Tech Stack

- **git** - バージョン管理（main直接プッシュ禁止、シークレット検出あり）
- **Python** / **uv** (pip禁止)
- **ruff** (lint/format) / **ty** (type check) / **pytest**
- `poe lint` / `poe test` / `poe all`

→ 詳細: `.claude/rules/dev-environment.md`, `.claude/rules/version-control.md`

---

## Documentation

| Location | Content |
|----------|---------|
| `.claude/rules/` | コーディング・セキュリティ・言語ルール |
| `.claude/docs/DESIGN.md` | 設計決定の記録 |
| `.claude/docs/research/` | Gemini調査結果 |
| `.claude/logs/cli-tools.jsonl` | Codex/Gemini入出力ログ |

---

## Language Protocol

- **思考・コード**: 英語
- **ユーザー対話**: 日本語
- **ユーザー向けコンテンツ**: 日本語（PR、コミット、エラーメッセージ）
- **絵文字**: 使用禁止（ユーザーが明示的に要求した場合のみ許可）

**ENFORCED BY HOOK**: `.claude/hooks/enforce-japanese.py` が PR/コミット作成時に日本語を強制

**IMPORTANT**: 絵文字は無駄であり、ユーザーは好みません。コミット、PR、ドキュメント、メッセージのすべてで絵文字を使用しないでください。

---

## Memory Layer (自己改善) ✓ 実装済み

ユーザーからの指示・修正・学習を**自動で**記憶し、自己改善に活用する。

### 自動動作

| タイミング | 動作 |
|-----------|------|
| **セッション開始** | 過去の記憶をコンテキストに自動注入 |
| **ユーザー修正時** | 「〜にして」等のパターンを自動検出・記憶 |

### 記憶の保存先

```
~/minions/.claude/memory/events.jsonl
```

### カテゴリ

| Category | 用途 | 自動検出 |
|----------|------|---------|
| `preference` | ユーザーの好み | ✓「〜にして」「〜がいい」 |
| `workflow` | ワークフローパターン | ✓「いつも〜」「毎回〜」 |
| `decision` | 設計判断 | - |
| `error` | エラーと解決策 | - |

### 使い方

```bash
# CLI
uv run python -m minions.memory.cli add "PRは日本語で書く" --type preference
uv run python -m minions.memory.cli search "日本語"
uv run python -m minions.memory.cli list

# Skill
/remember <学習内容>     # 記憶を保存
/remember list          # 一覧表示
/remember search <kw>   # 検索
```

### 自動学習トリガー ✓ 実装済み

以下のパターンを自動検出して記憶:

| パターン | 例 | 記憶タイプ |
|---------|-----|-----------|
| `〜にして` | 「PRは日本語にして」 | preference |
| `〜に変えて` | 「英語に変えて」 | preference |
| `〜は違う` | 「それは違う」 | preference |
| `いつも〜` | 「いつもテスト先に」 | workflow |
| `毎回〜` | 「毎回レビュー」 | workflow |

### Hooks（自動実行）

| Hook | 機能 |
|------|------|
| `load-memories.py` | セッション開始時に記憶を読み込み |
| `auto-learn.py` | ユーザー修正を自動検出・記憶 |

→ 詳細: `.claude/docs/MEMORY_SYSTEM.md`

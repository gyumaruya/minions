# 自己改善メモリシステム - 完全サイクル設計

## 概要

Claude Code マルチエージェント環境における自己改善メモリシステムの設計書。

### 設計原則

1. **Daemon 不要** — セッション稼働中のみ動作（ユーザー不在時はリソース消費ゼロ）
2. **Hook 駆動** — エージェント指示なしで絶対的・自動的に動作
3. **完全サイクル** — 記憶 → 整理 → 思い出す → 自己改善 が確実に回る

---

## サイクル全体図

```
┌─────────────────────────────────────────────────────────────────┐
│                      SESSION LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ RECORD   │───→│ ORGANIZE │───→│  RECALL  │───→│ IMPROVE  │  │
│  │  記憶    │    │   整理   │    │ 思い出す │    │ 自己改善 │  │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  │
│       │               │               │               │        │
│       ▼               ▼               ▼               ▼        │
│   PostToolUse     SessionEnd     SessionStart    SessionEnd    │
│   PostResponse    PostToolUse    PreToolUse      PostResponse  │
│                                                                 │
│       └───────────────┴───────────────┴───────────────┘        │
│                           ↑                                     │
│                           │                                     │
│                    次セッションへ継続                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4フェーズ詳細

### 1. RECORD（記憶）

**目的**: 経験・エラー・学習を記録する

| 項目 | 内容 |
|------|------|
| **トリガー** | PostToolUse, PostAssistantResponse |
| **記録内容** | 意図・計画、ツール実行結果、成功/失敗シグナル |
| **処理** | 正規化 → 初期スコア付与 → JSONL追記 + Hotキャッシュ |

**データフロー**:
```
HookEvent → 正規化 → 重要度スコア付与 → JSONL追記 + Hotキャッシュ
```

### 2. ORGANIZE（整理）

**目的**: 記憶を整理・圧縮・階層化する

| 項目 | 内容 |
|------|------|
| **トリガー** | PostToolUse(軽量/micro), SessionEnd(重量/macro) |
| **処理** | 重複排除、要約生成、tier遷移（Hot→Warm→Cold） |

**処理タイミング**:
- **micro（軽量）**: 毎 PostToolUse — 重要度再計算、重複イベント束ね
- **macro（重量）**: SessionEnd — セッション要約生成、Vector Index更新

**Tier 構造**:
| Tier | 期間 | 処理 |
|------|------|------|
| Hot | 0-7日 | 原文 + 軽い要約 |
| Warm | 7-30日 | 重要は詳細維持、他は中要約 |
| Cold | 30日+ | 長期要約に統合 |

### 3. RECALL（思い出す）

**目的**: 適切なタイミングで関連記憶を呼び出す

| 項目 | 内容 |
|------|------|
| **トリガー** | SessionStart(初期ブースト), PreToolUse(即時検索) |
| **関連性判定** | スコアリング + ルールベースブースト + ACLフィルタ |

**スコアリング式**:
```
Score = importance×0.4 + recency×0.3 + role_fit×0.2 + outcome×0.1
```

**ルールベースブースト**:
- 同一 task_id
- 直近の失敗パターン
- 成功パターン

### 4. SELF-IMPROVE（自己改善）

**目的**: 記憶を使って行動を改善する

| 項目 | 内容 |
|------|------|
| **トリガー** | PostAssistantResponse(暫定), SessionEnd(確定) |
| **処理** | 寄与度計算 → ポリシー自動更新 |

**寄与度計算**:
- 成功率向上
- 時間短縮
- ツール使用削減
- エラー回避

**自動ポリシー更新**:
- Retrieval 閾値調整（top-k、最低スコア）
- 重要度の重み調整（recency/novelty/outcome/role-fit）
- 低寄与パターンの除外ルール

**データフロー**:
```
取得メモリ + 結果シグナル → 寄与度計算 → ポリシー更新 → 次回RECALLパラメータ更新
```

---

## Hook → Phase マッピング

| Hook | RECORD | ORGANIZE | RECALL | IMPROVE |
|------|--------|----------|--------|---------|
| SessionStart | | | ✅ 初期注入 | |
| PreToolUse | | | ✅ 即時検索 | |
| PostToolUse | ✅ 結果記録 | ✅ micro整理 | | |
| PostResponse | ✅ 判断記録 | | | ✅ 暫定評価 |
| SessionEnd | | ✅ macro整理 | | ✅ 確定評価 |

---

## スコアリング

### 担当コンポーネント

| 処理 | 担当 | タイミング |
|------|------|-----------|
| 初期スコア | Memory Broker (Scoring Engine) | 書き込み直後（リアルタイム） |
| 再計算 | Memory Broker (SessionEnd) | セッション終了時（バッチ） |

**実装場所**: `src/minions/memory/scoring.py` に共通ロジック集約

### 重要度スコア式

```
Score = 0.25×成果 + 0.20×再利用 + 0.20×横断影響 + 0.15×新規性 + 0.15×ユーザーシグナル + 0.05×コスト削減
```

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                     Hook Router                          │
│  (SessionStart, PreToolUse, PostToolUse, SessionEnd)    │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Memory Broker                          │
│  - Scoring Engine (初期スコア + 再計算)                  │
│  - Compaction (tier遷移 + 要約生成)                      │
│  - Policy Manager (自己改善パラメータ)                   │
└─────────────┬───────────────────────────┬───────────────┘
              │                           │
              ▼                           ▼
     ┌──────────────┐            ┌──────────────┐
     │    JSONL     │            │    mem0      │
     │ (Source of   │            │ (Semantic    │
     │   Truth)     │            │   Search)    │
     └──────────────┘            └──────────────┘
```

---

## サブエージェント間の記憶共有

### 共通スキーマ

```json
{
  "agent_id": "musician-001",
  "role": "musician",
  "task_id": "task-123",
  "outcome": "success",
  "lessons": ["パターンA が有効", "パターンB は失敗"],
  "privacy": "agent-only"
}
```

### Privacy レベル

| レベル | 可視範囲 |
|--------|---------|
| private | 自分のみ |
| agent-only | 同一エージェント種別 |
| public | 全エージェント |

時限公開: `private → agent-only → public` の段階的移行

---

## 実装ファイル構成

| ファイル | 責務 |
|----------|------|
| `.claude/hooks/load-memories.py` | RECALL — SessionStart 時の記憶読み込み |
| `.claude/hooks/auto-learn.py` | RECORD — 自動学習の記録 |
| `src/minions/memory/broker.py` | Memory Broker — 書込API、スコアリング |
| `src/minions/memory/scoring.py` | Scoring Engine — 重要度計算（新規作成予定） |
| `src/minions/memory/compaction.py` | Compaction — tier判定と要約生成（新規作成予定） |

---

## 次のステップ

1. [ ] `scoring.py` — Scoring Engine 実装
2. [ ] `compaction.py` — Compaction Worker 実装
3. [ ] SessionEnd フック — macro整理 + 自己改善評価
4. [ ] PreToolUse フック — 即時検索の追加
5. [ ] Policy Manager — 自己改善パラメータ管理

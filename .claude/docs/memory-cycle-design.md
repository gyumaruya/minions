# Complete Self-Improving Memory Cycle Design

**Source:** Codex CLI (gpt-5.2-codex)
**Date:** 2026-02-02
**Status:** Complete Design Specification

---

## Overview

**完全自動・フック駆動・セッション内完結型**のメモリサイクル。

### Architecture Diagram

```
[SessionStart]
      |
      v
  (RECALL) <-------------------------------+
      |                                    |
      v                                    |
[PreToolUse] -> (RECORD) -> JSONL Log -> (ORGANIZE micro)
      |                                    |
      v                                    |
[PostToolUse] -> (RECORD) -> Feature/Score ->+
      |                                    |
      v                                    |
[PostAssistantResponse] -> (RECORD) -> Outcome Signals
      |                                    |
      v                                    |
 (SELF-IMPROVE) -> Policy Record -> Retrieval Params
      |                                    |
      v                                    |
[SessionEnd] -> (ORGANIZE macro) -> Summaries/Tiers -> Done
```

---

## Phase 1: RECORD

### Trigger Events

| Hook | What Gets Recorded |
|------|-------------------|
| **PreToolUse** | 意図、計画メタデータ、タスクコンテキスト |
| **PostToolUse** | 結果、成果物、エラー、実行時間、コスト |
| **PostAssistantResponse** | 生成内容、意図、成功/失敗シグナル |

### Data Captured

**Event Schema:**
```json
{
  "timestamp": "ISO-8601",
  "session_id": "uuid",
  "agent_role": "conductor|musician",
  "task_id": "uuid",
  "tool": "Edit|Bash|Grep|...",
  "inputs": {},
  "outputs": {},
  "status": "success|failure|partial",
  "latency_ms": 0,
  "error": null,
  "importance_score": 0.0,
  "signature": "hash",
  "acl": "session|user|agent"
}
```

### Data Flow

```
HookEvent
    → Normalize (standardize format)
    → Score (initial importance)
    → Sign & ACL (auth + scope)
    → JSONL append (SoT)
    → Hot cache (low-latency access)
```

---

## Phase 2: ORGANIZE

### Trigger Events

| Type | When | What Happens |
|------|------|--------------|
| **micro** | Every PostToolUse | 重要度再計算、重複束ね、hot→warm移送 |
| **macro** | SessionEnd | セッション要約生成、Tiered Cache更新 |

### Compaction Process

**Micro (Every PostToolUse):**
1. 重要度スコア再計算（outcome signals反映）
2. 重複/近接イベントの束ね
3. hot → warm 移送（閾値超過）

**Macro (SessionEnd):**
1. セッション全体の要約生成
2. hot/warm/cold境界サマリ作成
3. Vector Index更新（optional）

### Data Flow

```
JSONL events + hot cache
    → Micro: rescore + dedupe + tier shift
    → Macro: summarize + index
    → Summary Store + Tiered Cache + Vector Index
```

---

## Phase 3: RECALL

### Trigger Events

| Hook | Retrieval Strategy |
|------|--------------------|
| **SessionStart** | 初期ブースト取得（前回セッション要約） |
| **PreToolUse** | 直近タスク即時検索（context-aware） |

### Relevance Determination

**Scoring Formula:**
```
score = (importance × 0.4)
      + (recency × 0.3)
      + (role_fit × 0.2)
      + (outcome_contribution × 0.1)
```

**Rule-based Boosting:**
- 同一 task_id/agent_id → +0.2
- 直近失敗イベント → +0.3
- 成功パターン → +0.15

**ACL Filtering:**
- session: 現在セッションのみ
- user: すべてのセッション
- agent: 同一 agent_role のみ

### Data Flow

```
Task context (instruction + tool + files + recent results)
    → Rule-based filter (task_id/agent/recent failures)
    → Score ranking (importance × recency × role × outcome)
    → ACL filter (session/user/agent scope)
    → Retrieved memories + metadata (reason/source)
```

---

## Phase 4: SELF-IMPROVE

### Trigger Events

| Hook | Self-Improvement Action |
|------|------------------------|
| **PostAssistantResponse** | 暫定フィードバック（寄与度計算） |
| **SessionEnd** | 確定ポリシー更新 |

### Self-Improvement Mechanism

**Contribution Scoring:**

各取得メモリに対して寄与度を計算:
- 成功率向上 → +1.0
- 時間短縮 → +0.5
- ツール呼び出し削減 → +0.3
- エラー回避 → +0.8

**Policy Updates (Automatic):**

寄与度に基づいて以下を自動更新（JSONL に Policy Record として記録）:

1. **Retrieval 閾値調整**
   - top-k 値
   - 最低スコア閾値

2. **重要度の重み調整**
   - recency weight
   - novelty weight
   - outcome weight
   - role-fit weight

3. **除外/抑制ルール**
   - 低寄与の型を除外
   - ノイズパターン抑制

### Data Flow

```
Retrieved memories + outcome signals (success/failure/time/retries)
    → Contribution scoring (per memory)
    → Policy update calculation
    → Policy Record (JSONL append)
    → Next RECALL parameters update
```

---

## Hook Event to Phase Mapping

| Hook | RECORD | ORGANIZE | RECALL | SELF-IMPROVE |
|------|--------|----------|--------|--------------|
| **SessionStart** | - | micro (outbox) | ✓ | - |
| **PreToolUse** | ✓ | - | ✓ | - |
| **PostToolUse** | ✓ | micro | - | - |
| **PostAssistantResponse** | ✓ | - | - | ✓ (tentative) |
| **SessionEnd** | - | macro | - | ✓ (finalize) |

---

## Complete Automation Requirements

**絶対自動条件:**

1. **HookRouter が唯一の入口**
   - エージェント/ユーザー指示不要
   - すべてフック駆動

2. **JSONL が真の Source of Truth**
   - 派生データは再構築可能
   - 監査可能

3. **ジョブ分離**
   - micro: 毎フック（軽量）
   - macro: SessionEnd のみ（重量）

4. **ポリシー更新の透明性**
   - すべて JSONL に追記
   - ロールバック可能

---

## Verification Approach

### 1. Specification Verification

- **フック以外の動作なし**
  - 静的チェック: ジョブ起動は HookRouter のみ

- **決定性/再現性**
  - JSONL → 索引 → 取得の再構築テスト

### 2. Behavior Verification

- **RECALL 正答率/有用率**
  - 成功タスク比率
  - 再試行削減率

- **SELF-IMPROVE 改善度**
  - 前後比較（Policy Record diff）
  - 差分ログ分析

### 3. Safety Verification

- **スコープ ACL 漏洩ゼロ**
  - session/user/agent 境界テスト

- **誤学習防止**
  - 低寄与メモリの自動抑制が正しいか
  - 回帰テスト

### 4. Complete Automation

- **すべてのフェーズがセッション内で完結**
  - SessionStart → SessionEnd テスト
  - バックグラウンドプロセスなし検証

---

## Implementation Notes

**必須条件:**

- HookRouter が唯一の入口
- JSONL が真の SoT、派生は再構築可能
- micro ジョブは毎フック、macro ジョブは SessionEnd のみ
- ポリシー更新は必ず JSONL に追記（監査可能）

**Next Steps:**

この設計を `.claude/hooks` 既存フックに落とし込む具体仕様:
- イベントスキーマ
- 閾値設定
- 擬似コード/実装例

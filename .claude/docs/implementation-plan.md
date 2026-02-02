# Memory Cycle Implementation Plan

## Executive Summary

設計書（`.claude/docs/memory-cycle-design.md`）と現在の実装の差分を分析し、完全なメモリサイクル実装に向けた段階的実装計画を策定。

---

## 現状 vs 設計

### 1. RECORD（記憶）

#### ✅ 実装済み
- **Hook**: `auto-learn.py` (UserPromptSubmit)
- **記録内容**: ユーザーの修正・好み・ワークフローパターン
- **自動検出**: 正規表現パターンマッチング
- **データ永続化**: JSONL (`events.jsonl`)
- **Memory Broker**: 書き込みAPI (`broker.add()`)
- **スキーマ**: `MemoryEvent` 統一スキーマ
- **ACL**: `MemoryScope` によるアクセス制御
- **Redaction**: センシティブデータの自動マスキング

#### ❌ 未実装
- **PostToolUse フック**: ツール実行結果の記録
- **PostAssistantResponse フック**: エージェントの判断・計画の記録
- **初期スコア付与**: 重要度スコアの自動計算（Scoring Engine）
- **成功/失敗シグナルの記録**: outcome フィールドの自動設定

**Gap**: 現在は UserPrompt からの学習のみ。ツール実行結果やエージェントの判断は記録されていない。

---

### 2. ORGANIZE（整理）

#### ✅ 実装済み
- **データ構造**: `MemoryEvent` スキーマ
- **重複排除**: `load-memories.py` で content ベースの dedupe
- **TTL**: `ttl_days` フィールド、`broker.cleanup_expired()` メソッド

#### ❌ 未実装
- **micro 整理**: PostToolUse での軽量整理（重要度再計算、重複束ね）
- **macro 整理**: SessionEnd での重量整理（セッション要約生成）
- **Scoring Engine**: 重要度スコアリングロジック (`scoring.py`)
- **Compaction Worker**: Tier 遷移（Hot → Warm → Cold）と要約生成 (`compaction.py`)
- **Vector Index 更新**: SessionEnd での mem0 インデックス再構築
- **要約生成**: LLM を使った長文要約

**Gap**: 記憶は蓄積されるが整理・圧縮されない。長期的にはディスク/メモリ消費が増大。

---

### 3. RECALL（思い出す）

#### ✅ 実装済み
- **SessionStart Hook**: `load-memories.py`
- **関連記憶の注入**: preference, workflow, error を自動読み込み
- **JSONL 検索**: キーワードベースの検索 (`broker.search()`)
- **mem0 統合**: セマンティック検索サポート（API key がある場合）
- **ACL フィルタ**: `MemoryScope` によるフィルタリング

#### ❌ 未実装
- **PreToolUse Hook**: ツール実行前の即時検索
- **スコアリング式**: `importance×0.4 + recency×0.3 + role_fit×0.2 + outcome×0.1`
- **ルールベースブースト**: task_id 一致、失敗パターン、成功パターンによる優先度調整
- **Top-k 動的調整**: コンテキストに応じた取得件数の調整

**Gap**: SessionStart での初期注入のみ。ツール実行中の動的な記憶呼び出しは未実装。

---

### 4. SELF-IMPROVE（自己改善）

#### ✅ 実装済み
- **基本的な記憶蓄積**: 過去の経験を記録

#### ❌ 未実装
- **PostAssistantResponse Hook**: 暫定評価
- **SessionEnd Hook**: 確定評価
- **寄与度計算**: 記憶が結果にどれだけ貢献したか
- **ポリシー自動更新**: Retrieval 閾値、重要度の重み調整
- **低寄与パターン除外**: 役に立たなかった記憶の自動削除/降格
- **Policy Manager**: 自己改善パラメータの管理

**Gap**: 記憶を蓄積するだけで、それを使って行動を改善する仕組みがない。

---

## Hook イベント実装状況

| Hook Event | 設計での役割 | 現在の実装 | 優先度 |
|------------|-------------|-----------|--------|
| **SessionStart** | RECALL: 初期注入 | ✅ `load-memories.py` | — |
| **PreToolUse** | RECALL: 即時検索 | ❌ 未実装 | 高 |
| **PostToolUse** | RECORD + ORGANIZE(micro) | ❌ 未実装 | 高 |
| **PostResponse** | RECORD + IMPROVE(暫定) | ❌ 未実装 | 中 |
| **SessionEnd** | ORGANIZE(macro) + IMPROVE(確定) | ❌ 未実装 | 中 |

**Critical Gap**: PostToolUse が未実装のため、RECORD と ORGANIZE の主要な処理が動作していない。

---

## 未実装コンポーネント

| コンポーネント | ファイル | 責務 | 優先度 |
|--------------|---------|------|--------|
| **Scoring Engine** | `src/minions/memory/scoring.py` | 重要度スコア計算 | 高 |
| **Compaction Worker** | `src/minions/memory/compaction.py` | Tier 遷移、要約生成 | 中 |
| **Policy Manager** | `src/minions/memory/policy.py` | 自己改善パラメータ管理 | 低 |
| **PreToolUse Hook** | `.claude/hooks/pre-tool-recall.py` | 即時検索 | 高 |
| **PostToolUse Hook** | `.claude/hooks/post-tool-record.py` | 結果記録 + micro整理 | 高 |
| **SessionEnd Hook** | `.claude/hooks/session-end.py` | macro整理 + 確定評価 | 中 |

---

## 実装計画（3フェーズ）

### Phase 1: 基盤整備（RECORDの完成）

**目標**: ツール実行結果を記録し、基本的なスコアリングを実装する。

#### タスク

- [ ] **Scoring Engine 実装** (`scoring.py`)
  - 初期スコア計算式の実装
  - `成果×0.25 + 再利用×0.20 + 横断影響×0.20 + 新規性×0.15 + ユーザーシグナル×0.15 + コスト削減×0.05`
  - `broker.add()` で自動的にスコアを計算・保存

- [ ] **PostToolUse Hook 実装** (`post-tool-record.py`)
  - ツール実行結果（成功/失敗）を記録
  - `outcome` フィールドを自動設定
  - `context` にツール種別・実行時間を記録
  - Scoring Engine を呼び出して初期スコアを付与

- [ ] **設定ファイル更新** (`.claude/settings.json`)
  - PostToolUse フックに `post-tool-record.py` を追加

- [ ] **統合テスト**
  - ツール実行 → 記憶保存 → スコア付与の一連のフロー確認

**成果物**:
- `src/minions/memory/scoring.py`
- `.claude/hooks/post-tool-record.py`
- 更新された `.claude/settings.json`

**期待される効果**:
- ツール実行結果が自動的に記録される
- 記憶に重要度スコアが付与される
- RECORD フェーズが完全に機能する

---

### Phase 2: 動的 RECALL（即時検索）

**目標**: ツール実行前に関連記憶を動的に呼び出す。

#### タスク

- [ ] **PreToolUse Hook 実装** (`pre-tool-recall.py`)
  - ツール種別・パラメータから関連記憶を検索
  - スコアリング式で関連度を計算
  - Top-k 記憶をコンテキストに注入

- [ ] **スコアリング式の実装** (`scoring.py` に追加)
  - `importance×0.4 + recency×0.3 + role_fit×0.2 + outcome×0.1`
  - ルールベースブースト（task_id 一致、失敗パターン）

- [ ] **設定ファイル更新** (`.claude/settings.json`)
  - PreToolUse フックに `pre-tool-recall.py` を追加

- [ ] **統合テスト**
  - ツール実行前 → 記憶検索 → コンテキスト注入の確認
  - 過去の失敗パターンが適切に警告されるか

**成果物**:
- `.claude/hooks/pre-tool-recall.py`
- 更新された `src/minions/memory/scoring.py`
- 更新された `.claude/settings.json`

**期待される効果**:
- ツール実行前に関連記憶が自動的に呼び出される
- 過去の失敗パターンを事前に回避できる
- RECALL フェーズが動的に機能する

---

### Phase 3: ORGANIZE & IMPROVE（整理と自己改善）

**目標**: 記憶を整理・圧縮し、自己改善ループを回す。

#### タスク

- [ ] **Compaction Worker 実装** (`compaction.py`)
  - Tier 判定ロジック（Hot 0-7日、Warm 7-30日、Cold 30日+）
  - 要約生成（LLM を使った長文圧縮）
  - JSONL ファイルの再編成

- [ ] **SessionEnd Hook 実装** (`session-end.py`)
  - セッション要約の生成
  - Compaction Worker を呼び出し（macro 整理）
  - 寄与度計算（記憶がどれだけ役立ったか）
  - Policy 自動更新（低寄与記憶の除外）

- [ ] **Policy Manager 実装** (`policy.py`)
  - Retrieval パラメータの管理（top-k、最低スコア）
  - 重要度の重み調整（recency/novelty/outcome/role-fit）
  - 低寄与パターンの除外ルール

- [ ] **設定ファイル更新** (`.claude/settings.json`)
  - SessionEnd フックに `session-end.py` を追加

- [ ] **統合テスト**
  - セッション終了時の整理・要約生成の確認
  - 寄与度計算の妥当性確認
  - 低寄与記憶が適切に除外されるか

**成果物**:
- `src/minions/memory/compaction.py`
- `src/minions/memory/policy.py`
- `.claude/hooks/session-end.py`
- 更新された `.claude/settings.json`

**期待される効果**:
- 記憶が自動的に整理・圧縮される
- 長期的なディスク使用量が管理される
- 自己改善ループが回り、記憶の質が向上する
- システムが時間とともに賢くなる

---

## 実装順序の理由

1. **Phase 1 優先**: RECORD が完成しないと、データが蓄積されない
2. **Phase 2 次**: RECALL が機能しないと、記憶が活用されない
3. **Phase 3 最後**: ORGANIZE/IMPROVE は長期的な最適化であり、Phase 1/2 の動作確認後に実装

---

## リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| **スコアリング計算コスト** | ツール実行が遅くなる | 軽量な計算式、バッチ処理 |
| **mem0 API コスト** | OpenAI API 料金 | Keychain からの API key 取得、fallback to JSONL |
| **Hook タイムアウト** | Hook が失敗する | タイムアウト時間を適切に設定（5-10秒） |
| **記憶の爆発的増加** | ディスク使用量増大 | TTL、Compaction Worker |
| **低品質な記憶** | ノイズが多い | 初期スコアでフィルタ、低寄与パターン除外 |

---

## 成功指標

### Phase 1 完了時
- [ ] ツール実行結果が自動記録される
- [ ] 記憶に重要度スコアが付与される
- [ ] `broker.get_stats()` で記録数が増加している

### Phase 2 完了時
- [ ] ツール実行前に関連記憶が呼び出される
- [ ] 過去の失敗パターンが警告される
- [ ] エージェントが過去の経験を活用している

### Phase 3 完了時
- [ ] セッション終了時に記憶が整理される
- [ ] 記憶が Tier 遷移する（Hot → Warm → Cold）
- [ ] 低寄与記憶が自動的に除外される
- [ ] システムが時間とともに改善している

---

## Next Actions

1. **Phase 1 開始**: `src/minions/memory/scoring.py` の実装
2. **PostToolUse Hook**: `.claude/hooks/post-tool-record.py` の作成
3. **統合テスト**: ツール実行 → 記録 → スコア付与のフロー確認

---

## Appendix: 設計書との対応表

| 設計書セクション | 実装状況 | 対応 Phase |
|-----------------|---------|-----------|
| RECORD - PostToolUse | ❌ | Phase 1 |
| RECORD - PostResponse | ❌ | Phase 1 |
| ORGANIZE - micro | ❌ | Phase 1 |
| ORGANIZE - macro | ❌ | Phase 3 |
| RECALL - SessionStart | ✅ | 完了 |
| RECALL - PreToolUse | ❌ | Phase 2 |
| IMPROVE - 寄与度計算 | ❌ | Phase 3 |
| IMPROVE - ポリシー更新 | ❌ | Phase 3 |
| Scoring Engine | ❌ | Phase 1 |
| Compaction Worker | ❌ | Phase 3 |
| Policy Manager | ❌ | Phase 3 |

---

## まとめ

現在の実装は RECORD と RECALL の基礎部分（ユーザー修正の学習、セッション開始時の記憶注入）のみ。

**完全なメモリサイクル実現には以下が必要:**

1. **Phase 1 (高優先度)**: Scoring Engine + PostToolUse Hook → ツール実行結果の記録
2. **Phase 2 (高優先度)**: PreToolUse Hook → 動的な記憶呼び出し
3. **Phase 3 (中優先度)**: Compaction + SessionEnd Hook → 整理と自己改善

**推定工数:**
- Phase 1: 2-3日
- Phase 2: 2-3日
- Phase 3: 4-5日
- **合計: 8-11日**（統合テスト含む）

---

**Document Version**: 1.0
**Author**: Musician (Richard Feynman)
**Date**: 2026-02-02
**Status**: Draft

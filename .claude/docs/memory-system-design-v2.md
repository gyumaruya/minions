# Memory System Design v2: Self-Improving Multi-Agent Memory

**Design Consultation with Codex CLI**
Date: 2026-02-01

## Architecture Overview

```text
                    ┌───────────────────────────────────────────┐
                    │              Hook Router                  │
                    │ PreToolUse / PostToolUse / PostResponse    │
                    │ SessionStart / SessionEnd / Error          │
                    └───────────────┬───────────────┬────────────┘
                                    │               │
                                    │ retrieve       │ record
                                    ▼               ▼
┌──────────────┐   read/write   ┌────────────────────────┐   append   ┌──────────────┐
│ Conductor    │───────────────▶│    Memory Broker       │───────────▶│ JSONL SoT    │
│ (Claude)     │◀───────────────│ (schema/ACL/summarize) │            │ (event log)  │
└──────────────┘   context inj. └──────────┬─────────────┘            └──────────────┘
                                           │
                                           │ index/update
                                           ▼
                                  ┌───────────────────┐
                                  │ Vector Index      │
                                  │ (mem0)            │
                                  └───────────────────┘
                                           │
                                           │ derived
                                           ▼
                                  ┌───────────────────┐
                                  │ Profile Store     │
                                  │ (prefs, facts)    │
                                  └───────────────────┘

Other agents (Musician/Codex/Gemini/Copilot) ↔ Memory Broker
```

## Hook Event Matrix

### Write Triggers (記録)

| Hook Point | What to Record | Priority |
|------------|---------------|----------|
| **PreToolUse** | Task intent, planning, user instructions | High |
| **PostToolUse** | Tool results, success/failure, cost, artifact metadata | High |
| **PostAssistantResponse** | Final answer, decisions, user approval/rejection | High |
| **SessionStart** | Session goal, scope, participating agents | Medium |
| **SessionEnd** | Results summary, unresolved issues, next actions | High |
| **Error/Exception** | Failure cause, reproduction conditions, workaround | Critical |

### Read Triggers (取得)

| Hook Point | What to Retrieve | Context |
|------------|------------------|---------|
| **PreToolUse** | Similar tasks, procedures, constraints | Task-specific |
| **PreAssistantResponse** | Recent conversation + important memories | Session + global |
| **AgentSwitch** | Role-specific memories | Agent-specific |
| **SessionStart** | User preferences, project policies | Global |
| **TaskBoundary** | Relevant memories for new task | Task-specific |

## Memory Flow

### Write Flow

```text
User/Agent Action
   └─(Hook)──> Event Normalizer ──> Memory Broker
                                    ├─ validate schema/ACL
                                    ├─ enrich (agent_id, role, task, outcome)
                                    ├─ importance scoring
                                    ├─ write JSONL SoT (append-only)
                                    └─ async: update mem0 index + summaries
```

### Read Flow

```text
Task/Response Trigger
   └─(Hook)──> Query Builder
                 ├─ scope: session/user/agent
                 ├─ intent keywords
                 ├─ recency/importance filters
                 └─ conflict detection
              └─> Memory Broker
                     ├─ fetch JSONL (exact matches)
                     ├─ mem0 semantic search
                     ├─ rank + de-dup + compress
                     └─ inject into context
```

## Subagent Experience Capture

### Common Envelope Schema

All agent experiences share a common structure:

```json
{
  "agent_id": "conductor|musician|codex|gemini|copilot",
  "role": "orchestrator|executor|reasoner|researcher|general",
  "task_id": "uuid",
  "intent": "user's original request",
  "actions": ["tool1", "tool2"],
  "outcome": "success|failure|partial",
  "artifacts": ["file1.py", "docs/design.md"],
  "errors": ["error message", "stack trace"],
  "lessons": "key learnings from this task",
  "cost": {"tokens": 1000, "time_ms": 5000},
  "privacy": "public|agent-only|private",
  "expires_at": "2026-03-01T00:00:00Z"
}
```

### Sharing Rules

- **Agent → Broker**: All agents send experiences to Memory Broker
- **ACL Enforcement**: Broker checks privacy level and sharing permissions
- **Time-based Sharing**: Private memories can become shared after certain period
- **Cross-agent Learning**: Public memories are available to all agents

### Privacy Levels

| Level | Description | Shared With |
|-------|-------------|-------------|
| `public` | Available to all agents | All |
| `agent-only` | Only for specific agent type | Same agent role |
| `private` | Session-specific | Current session only |

## Compaction & Consolidation Strategy

### Three-Tier Hot/Warm/Cold

| Tier | Age | Storage | Compaction |
|------|-----|---------|------------|
| **Hot** | 0-7 days | Full events + short summaries | Minimal |
| **Warm** | 7-30 days | Important events detailed, others summarized | Medium |
| **Cold** | 30+ days | Long-term summaries only, low-importance archived | Heavy |

### Multi-Stage Summarization

```text
Individual Events
    ↓ (daily)
Task Summaries
    ↓ (weekly)
Session Summaries
    ↓ (monthly)
Project Summaries
```

### Conflict Management

- **Don't Delete Failures**: Keep counter-examples as "refuted summaries"
- **Version Conflicts**: Mark as "approach A vs approach B" with contexts
- **Superseded Knowledge**: Link old → new with "superseded_by" relationship

## Importance Scoring

### Scoring Factors

| Factor | Weight | Notes |
|--------|--------|-------|
| **Outcome Impact** | 0.25 | Success or failure (both important) |
| **Reuse Frequency** | 0.20 | How often referenced |
| **Cross-Agent Impact** | 0.20 | Multiple agents/tasks involved |
| **Novelty** | 0.15 | Difference from existing knowledge |
| **User Signal** | 0.15 | Explicit approval/rejection |
| **Cost Savings** | 0.05 | Time/token reduction achieved |

### Score Calculation

```python
importance_score = (
    0.25 * outcome_impact +
    0.20 * reuse_frequency +
    0.20 * cross_agent_impact +
    0.15 * novelty +
    0.15 * user_signal +
    0.05 * cost_savings
)
```

### Score-Based Actions

| Score Range | Action |
|-------------|--------|
| 0.8 - 1.0 | Keep full detail indefinitely |
| 0.6 - 0.8 | Keep detailed for 30 days, then summarize |
| 0.4 - 0.6 | Keep detailed for 7 days, then summarize |
| 0.0 - 0.4 | Summarize immediately, archive after 30 days |

## Optimal Architecture Components

### Core Components

1. **Hook Router** - Event dispatcher (PreToolUse, PostToolUse, etc.)
2. **Memory Broker** - Central coordinator (ACL, scoring, read/write)
3. **JSONL SoT** - Source of truth (append-only log)
4. **mem0 Vector Index** - Semantic search layer
5. **Profile Store** - Derived preferences and facts

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Two-layer storage** | JSONL for durability, mem0 for search |
| **Broker pattern** | Centralized ACL and compression |
| **Async indexing** | Don't block main workflow |
| **Multi-stage compaction** | Balance detail vs context size |
| **Score-based lifecycle** | Automatic importance-driven cleanup |

## Implementation Priorities

### Phase 1: Foundation (Week 1-2)
1. Canonical event schema + ACL
2. JSONL source of truth
3. Memory Broker MVP (write/read API)

### Phase 2: Intelligence (Week 3-4)
4. Importance scoring system
5. Hot/warm/cold lifecycle management
6. mem0 indexing + retrieval ranking

### Phase 3: Advanced (Week 5-6)
7. Multi-stage summarization pipeline
8. Cross-agent sharing policies
9. Audit UI and debug tools

## Next Steps

Choose what to implement next:

1. **JSONL Schema Design** - Define exact event format
2. **Hook Router Implementation** - Event definitions and pseudocode
3. **Importance Scoring Weights** - Fine-tune scoring factors
4. **mem0 Ranking Strategy** - Search, dedup, and ranking logic

## 実装状況（2026-02-04）

### 実装済み: Phase 1（部分的）

**JSONL Source of Truth:**
- ✅ グローバル記憶パス: `~/.config/ai/memory/events.jsonl`
- ✅ `MemoryEvent` スキーマ（Rust: `hook-memory` クレート）
- ✅ Append-only JSONL ログ

**Rust フック:**
- ✅ `load-memories` - セッション開始時に読み込み
- ✅ `auto-learn` - ユーザー修正の自動学習
- ✅ `pre-tool-recall` - ツール実行前の記憶参照
- ✅ `post-tool-record` - ツール実行結果の記録

**未実装:**
- ❌ Memory Broker（統一API、スキーマ検証、要約）
- ❌ mem0 ベクトル索引
- ❌ Importance scoring
- ❌ Hot/warm/cold lifecycle
- ❌ Multi-stage summarization

### 次のステップ

1. **Phase 2: ローカル記憶の追加** - プロジェクト固有の記憶分離
2. **Memory Broker 実装** - このドキュメントの設計に従う
3. **mem0 統合** - ベクトル検索の追加

## References

- 実装済み: `~/.config/ai/memory/events.jsonl`
- Rust フック: `hooks-rs/crates/hooks/{load-memories,auto-learn,pre-tool-recall,post-tool-record}`
- スキーマ: `hooks-rs/crates/hook-memory/src/schema.rs`
- Documentation: `.claude/docs/MEMORY_SYSTEM.md`, `.claude/docs/GLOBAL_CONFIG_DESIGN.md`

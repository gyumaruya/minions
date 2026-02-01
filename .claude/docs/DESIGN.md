# Project Design Document

> This document tracks design decisions made during conversations.
> Updated automatically by the `design-tracker` skill.

## Overview

Multi-agent AI system memory architecture guidance for orchestrating Claude Code, Codex CLI, Gemini CLI, and Copilot CLI with layered memory (session/user/agent) and cross-agent sharing.

## Architecture

Canonical memory event log (append-only JSONL) as source of truth, plus optional vector index for retrieval. Introduce a Memory Broker service that normalizes writes from all agents, performs summarization, and manages read routing based on scope (session/user/agent).

```
Claude Code (orchestrator)
  -> Memory Broker (write/read API, schema validation, summarizer)
      -> JSONL Event Store (SoT, immutable, auditable)
      -> Vector Index (mem0 or equivalent) for semantic retrieval
      -> User Profile Store (derived, curated preferences)
Other agents (Codex/Gemini/Copilot) <-> Memory Broker
```

Extended hook-driven design: a Hook Router triggers write/read flows on PreToolUse, PostToolUse, PostAssistantResponse, and SessionBoundary events, coordinating Memory Broker writes and retrieval injection per scope and role. A background Memory Orchestrator handles retries, batch scoring recalibration, and compaction when no agent is active.

Hook-based delegation enforcement for the Conductor/Section Leader lives at the Claude Code hook layer (PreToolUse). It uses file-based session state to track "non-delegated work tool usage" and blocks or warns when thresholds are exceeded, while preserving a small allowlist for config edits (e.g., `.claude/`).

Self-improving memory is a hook-driven, session-only cycle with four phases: Record, Organize, Recall, Self-Improve. It runs only during active sessions and uses hook events (SessionStart, Pre/PostToolUse, PostAssistantResponse, SessionEnd) to capture events, compact memories, retrieve context, and update policies. No background daemon is required; all maintenance runs as hook-triggered, bounded jobs.

Memory is stored as an append-only JSONL event log (canonical), plus derived artifacts: a compacted summary store, a tiered cache (hot/warm/cold), and optional vector index for semantic retrieval. Each event includes a stable ID, scope, ACL, agent role, task metadata, outcome signals, and an importance score. Summaries are generated at tier boundaries and on session end.

Self-improvement uses a policy feedback loop: retrieval outcomes and task results update scoring weights and retrieval thresholds per role (Conductor/Musician) and per scope. Updates are stored as versioned policy records in the JSONL log and applied on subsequent sessions via SessionStart hook.

## Implementation Plan

### Patterns & Approaches

<!-- Design patterns, architectural approaches -->

| Pattern | Purpose | Notes |
|---------|---------|-------|
| Event-sourced memory log | Auditability, deterministic rebuilds | JSONL as canonical SoT; derived indexes are rebuildable |
| Write-through cache | Fast retrieval | Vector index mirrors JSONL, can be rebuilt |
| Scoped memory routing | Reduce leakage | Session/User/Agent scopes with explicit ACL |
| Summarization pipeline | Memory compression | Periodic distillation to reduce context |
| Hook-based delegation enforcement | Prevent upper agents from direct work | PreToolUse hook with per-session counters and allowlist |
| Hook-driven memory I/O | Automatic capture/retrieval | Hooks for tool boundaries, responses, and session lifecycle |
| Multi-stage compaction | Lifecycle management | Hot/warm/cold tiers with progressive summarization |
| Self-improving memory loop | Continuous improvement without daemon | Hook-driven feedback updates scoring/retrieval policy |

### Libraries & Roles

<!-- Libraries and their responsibilities -->

| Library | Role | Version | Notes |
|---------|------|---------|-------|
| mem0 | Vector memory store/retriever | TBD | Optional semantic index, not SoT |

### Key Decisions

<!-- Important decisions and their rationale -->

| Decision | Rationale | Alternatives Considered | Date |
|----------|-----------|------------------------|------|
| Prefer hybrid memory (JSONL SoT + vector index) | Auditability + semantic retrieval | Pure JSONL, pure vector store | 2026-01-31 |
| Introduce Memory Broker service | Consistent schema, routing, summaries | Direct agent-to-store writes | 2026-01-31 |
| Standardize canonical event schema | Cross-agent sharing with minimal coupling | Agent-specific schemas | 2026-01-31 |
| Embedding provider abstraction | Provider agility and cost/latency control | Single-provider lock-in | 2026-01-31 |
| Enforce delegation via PreToolUse hook with per-session state | Block prolonged direct work by Conductor/Section Leader | Stateless-only hooks, manual policing | 2026-01-31 |
| Identify agent role via AGENT_ROLE env var with safe defaults | Clear separation of conductor/section leader/musician | Prompt parsing only, file markers only | 2026-01-31 |
| Use file marker as fallback only (session id + lock) | Avoid misclassification if AGENT_ROLE missing | PPID heuristics, marker-only primary | 2026-01-31 |
| Prefer 2-tier (Conductor → Musician) as CLI default; 3-tier only when coordination or permission boundaries justify it | Lower latency and simpler debugging for CLI workflows; 3-tier reserved for large parallel workstreams | Always 3-tier, always 2-tier | 2026-01-31 |
| Trigger memory I/O via hook router (tool boundaries + response + session) | Automatic capture/retrieval without explicit commands | Manual save/load, ad-hoc prompts | 2026-02-01 |
| Use multi-tier lifecycle (hot/warm/cold) with progressive compaction | Balance recall quality and storage cost | Single summary pass, TTL-only eviction | 2026-02-01 |
| Use importance scoring with utility signals (usage, outcomes, novelty, conflicts) | Prioritize high-value memories for retrieval | Recency-only, static priority | 2026-02-01 |
| Use hybrid scoring (real-time ingest + batch recalibration) | Timely ranking with long-horizon adjustments | Batch-only, real-time-only | 2026-02-01 |
| Run compaction and retries in a background orchestrator | Ensures automation even without active agents | Hooks-only processing | 2026-02-01 |
| Store retries in durable outbox with idempotent handlers | Failure recovery and replayability | Best-effort only | 2026-02-01 |
| Implement self-improving memory as hook-driven cycle only | Satisfy no-daemon constraint while remaining automatic | Background scheduler | 2026-02-01 |
| Run all compaction, scoring updates, and retry/outbox drains only on hook events | Enforce "no daemon" constraint and ensure bounded work per active session | Background worker, cron | 2026-02-01 |
| Use policy records that update retrieval thresholds and scoring weights from observed outcomes | Make self-improvement measurable and auditable | Static heuristics, manual tuning | 2026-02-01 |
| Use tiered memory (hot/warm/cold) with boundary summaries | Reduce context size while preserving signal | Flat store | 2026-02-01 |
| Update scoring and retrieval policy from observed outcomes | Continuous improvement with measurable feedback | Static heuristics | 2026-02-01 |

## TODO

<!-- Features to implement -->

- [ ] Define canonical memory event schema and ACL fields
- [ ] Design summarization schedule and retention policy
- [ ] Implement rebuildable vector index pipeline
- [ ] Implement delegation enforcement state tracking hook (counters + thresholds)
- [ ] Implement hook router to coordinate memory read/write triggers
- [ ] Define importance scoring model and lifecycle thresholds
- [ ] Add cross-agent experience capture envelope (agent_id, role, task, outcome)
- [ ] Define Memory Orchestrator (scheduler, retries, batch scoring, compaction)
- [ ] Add durable outbox + idempotent replay for hook writes
- [ ] Specify hook-to-phase mapping table and event schema for memory cycle
- [ ] Implement policy feedback records and per-role retrieval thresholds
- [ ] Add verification checklist and metrics logging for cycle completeness

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] Which embedding model/provider becomes the default?
- [ ] What is the optimal granularity for shared agent memory?
- [ ] How aggressively should negative/failed attempts be retained vs. summarized?
- [ ] Should per-agent private memories be allowed to auto-share after cooldown?
- [ ] Which outcome signals best predict beneficial memories (time saved, fewer tool calls, fewer errors)?

## Changelog

| Date | Changes |
|------|---------|
| 2026-01-31 | Added multi-agent memory architecture recommendations and decisions |
| 2026-01-31 | Added hook-based delegation enforcement design decisions |
| 2026-01-31 | Added fallback strategy for agent role detection |
| 2026-01-31 | Recorded default hierarchy recommendation (2-tier for CLI; 3-tier for large coordinated work) |
| 2026-02-01 | Added hook-driven memory I/O, lifecycle compaction, and importance scoring decisions |
| 2026-02-01 | Added hybrid scoring, background orchestrator, and durable retry decisions |
| 2026-02-01 | Added self-improving hook-driven memory cycle design |
| 2026-02-01 | Clarified no-daemon enforcement and policy-based self-improvement records |

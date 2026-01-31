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

Hook-based delegation enforcement for the Conductor/Section Leader lives at the Claude Code hook layer (PreToolUse). It uses file-based session state to track "non-delegated work tool usage" and blocks or warns when thresholds are exceeded, while preserving a small allowlist for config edits (e.g., `.claude/`).

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

## TODO

<!-- Features to implement -->

- [ ] Define canonical memory event schema and ACL fields
- [ ] Design summarization schedule and retention policy
- [ ] Implement rebuildable vector index pipeline
- [ ] Implement delegation enforcement state tracking hook (counters + thresholds)

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] Which embedding model/provider becomes the default?
- [ ] What is the optimal granularity for shared agent memory?

## Changelog

| Date | Changes |
|------|---------|
| 2026-01-31 | Added multi-agent memory architecture recommendations and decisions |
| 2026-01-31 | Added hook-based delegation enforcement design decisions |
| 2026-01-31 | Added fallback strategy for agent role detection |
| 2026-01-31 | Recorded default hierarchy recommendation (2-tier for CLI; 3-tier for large coordinated work) |

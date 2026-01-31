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

## Implementation Plan

### Patterns & Approaches

<!-- Design patterns, architectural approaches -->

| Pattern | Purpose | Notes |
|---------|---------|-------|
| Event-sourced memory log | Auditability, deterministic rebuilds | JSONL as canonical SoT; derived indexes are rebuildable |
| Write-through cache | Fast retrieval | Vector index mirrors JSONL, can be rebuilt |
| Scoped memory routing | Reduce leakage | Session/User/Agent scopes with explicit ACL |
| Summarization pipeline | Memory compression | Periodic distillation to reduce context |

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

## TODO

<!-- Features to implement -->

- [ ] Define canonical memory event schema and ACL fields
- [ ] Design summarization schedule and retention policy
- [ ] Implement rebuildable vector index pipeline

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] Which embedding model/provider becomes the default?
- [ ] What is the optimal granularity for shared agent memory?

## Changelog

| Date | Changes |
|------|---------|
| 2026-01-31 | Added multi-agent memory architecture recommendations and decisions |

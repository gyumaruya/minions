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

### Layered Config/Memory System (Global + Project)

Introduce a lightweight, layered configuration/memory architecture that separates stable user memory from volatile tool-specific configs. The system favors simple file structures and symlinks, supports graceful degradation when tools evolve, and allows both global and per-project overrides without heavy dependencies.

**Design Proposal (Codex):**
```
Global (stable, shared)
  ~/.ai/
    memory/          # user preferences, workflows, learnings (tool-agnostic)
    policies/        # stable rules/guardrails (tool-agnostic)
    profiles/        # optional role/persona presets
    tools/           # tool shims + compatibility mappings

Project (scoped, override)
  .ai/
    memory/          # project-specific learnings
    policies/        # project guardrails
    tools/           # tool-specific overrides for this repo
```

**Implemented (2026-02-04):**
```
Global (XDG Base Directory compliant)
  ~/.config/ai/
    hooks/bin/       # symlink to minions/hooks-rs/target/release
    memory/          # events.jsonl (global memory)

  ~/.claude/
    settings.json    # global hooks definition (23 hooks)

Project (minimal override)
  <project>/.claude/
    settings.json    # project-specific env/overrides only
```

**Key Differences:**
- Used `~/.config/ai/` instead of `~/.ai/` (XDG compliance)
- Simplified to memory + hooks only (no policies/profiles/tools yet)
- Hooks managed via `~/.claude/settings.json` (Claude Code native)
- Phase 1: Global memory only; local memory TBD

Resolution order: Project overrides Global; tool-specific configs read from `.ai/tools/<tool>/` then fallback to `~/.ai/tools/<tool>/` and finally to tool defaults. Stable memory remains tool-agnostic and is referenced by tools via simple adapters.

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
| serde + serde_json | JSON I/O for hooks and memory events | TBD | Std JSON stdin/stdout, JSONL |
| regex | Pattern matching in hooks | TBD | Replace Python re usage |
| camino | UTF-8 friendly paths | TBD | Cross-platform path handling |
| tempfile | Temp files/dirs | TBD | Replace /tmp assumptions |
| fs2 | File locks | TBD | Atomic state handling across OS |
| tracing | Structured logging | TBD | Hook diagnostics |
| thiserror/anyhow | Error handling | TBD | Consistent error surfaces |
| assert_cmd + predicates | CLI integration tests | TBD | Cross-platform hook tests |
| insta | Snapshot/golden tests | TBD | JSON stdout snapshotting for hooks |
| jsonschema (or schemars) | Contract tests for hook I/O | TBD | Validate stdin/stdout structure |

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
| Store delegation enforcement state under project-controlled `.claude/.delegation-state/` with atomic writes and missing-state warnings | Reduce `/tmp` tampering and make enforcement state auditable | Keep state in `/tmp`, rely on delete-block hooks | 2026-02-02 |
| Migrate hook executables toward Rust binaries; allow compiled Python (PyInstaller/Nuitka) as short-term stabilization | Rust provides single static-ish binaries, strong typing, predictable runtime; compiled Python reduces env drift quickly | Stay on pure Python, move to Go | 2026-02-02 |
| Keep Memory Broker as a Python sidecar service during early hook migration | Minimizes risk; preserves mem0 integration while hooks are stabilized | Full Rust port immediately | 2026-02-02 |
| Introduce cross-platform hook test harness with JSON fixtures and snapshot outputs | Prevent regressions across macOS/Linux/Windows | Manual testing only | 2026-02-02 |
| Use record/replay fixtures to capture Python hook stdin/stdout and run differential tests against Rust | Ensures behavioral parity during migration | Handwritten tests only, manual spot checks | 2026-02-02 |
| Organize hook fixtures per hook with golden outputs + error cases | Scales to 24 hooks and keeps parity checks focused | Monolithic fixture file | 2026-02-02 |
| Normalize JSON in parity tests (sorted keys, filtered volatile fields) | Prevents flaky diffs while preserving behavior | Raw text compare only | 2026-02-02 |
| Use per-hook fixture folders with case metadata + stdin.json + expected.json | Keeps fixtures readable and supports re-recording | Ad-hoc file naming | 2026-02-02 |
| Prefer differential tests (Python vs Rust) + snapshots for stdout/stderr | Strong parity guarantee plus readable diffs | Snapshot-only or unit-only | 2026-02-02 |
| Separate stable memory/policies from tool-specific configs using a layered file structure (Global + Project) | Persist user learnings while allowing tools to evolve without breaking memory | Monolithic per-tool configs, single global file | 2026-02-03 |
| Use simple fallback resolution and symlink-friendly paths for tool configs | Minimal footprint and graceful degradation when tools change | Centralized config service, database-backed configs | 2026-02-03 |
| Keep tool adaptation in small shims/mappings under `tools/` | Isolates volatility and simplifies migration | Embedding tool rules into memory layer | 2026-02-03 |
| Introduce explicit Tool Adapter + Hook Capability layer with versioned contracts | Decouple fast-changing CLIs from stable memory/storage and allow graceful fallback | Hardcode hook behavior per tool | 2026-02-03 |
| Version memory schema and hook I/O with semver and per-event schema_version fields | Enables forward/backward compatibility and safe migrations | Implicit schema evolution | 2026-02-03 |
| Add a migration tool that replays JSONL into a new schema and rebuilds derived indexes | Deterministic upgrades without data loss | In-place mutation of JSONL | 2026-02-03 |
| Fail when no stable base directory exists (HOME missing) and avoid relative fallbacks; resolve memory path in order: AI_MEMORY_PATH → OS config dir (XDG) → error | Predictable paths and explicit failure over cwd-dependent behavior | Relative fallback, implicit cwd usage | 2026-02-04 |
| Make default_path return Result<Utf8PathBuf, Error> to surface missing base dir and allow callers to handle | Avoid silent fallbacks and simplify error reporting | Always returning a path with fallback | 2026-02-04 |
| Introduce PermissionRequest auto-approval triage (denylist/allowlist/LLM fallback) with fail-closed timeouts and no-shell execution | Reduce approval friction while keeping destructive commands blocked and uncertain cases explicit | Manual-only approvals, regex-only allow/deny without fallback | 2026-02-04 |

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
- [ ] Define hook binary build/release pipeline for macOS/Linux/Windows
- [ ] Define hook stdin/stdout JSON contract tests and fixture library
- [ ] Add record/replay tool to capture Python hook behavior into fixtures
- [ ] Add differential test runner that executes Python vs Rust and compares JSON outputs
- [ ] Define Memory Broker IPC boundary for non-Python hooks (stdin/stdout or local socket)
- [ ] Define JSON normalization rules (volatile field filters, ordering) for parity tests
- [ ] Create fixture format spec (case metadata, stdin.json, expected.json, notes)
- [ ] Define Tool Adapter interface (capabilities, events, routing rules, fallbacks)
- [ ] Define Hook Capability manifest (supported hooks, tool versions, schema range)
- [ ] Implement migration tool (replay + rebuild) with dry-run and audit report
- [ ] Add schema_version field to memory events and hook I/O contracts
- [ ] Define command normalization/parsing for PermissionRequest classifier (argv-based, not raw string only)
- [ ] Add adversarial test corpus for command obfuscation (shell expansion, separators, encoded payloads)
- [ ] Add timeout/circuit-breaker policy for LLM fallback in approval hooks

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] Which embedding model/provider becomes the default?
- [ ] What is the optimal granularity for shared agent memory?
- [ ] How aggressively should negative/failed attempts be retained vs. summarized?
- [ ] Should per-agent private memories be allowed to auto-share after cooldown?
- [ ] Which outcome signals best predict beneficial memories (time saved, fewer tool calls, fewer errors)?
- [ ] How should cross-tool identity be mapped (user/agent IDs) without leaking tool-specific identifiers?
- [ ] Do we need a global/local split at all, or is a single per-project JSONL log sufficient?
- [ ] Is hook versioning via manifest.json necessary, or can we rely on the hook binary itself (or none)?
- [ ] Should ambiguous PermissionRequest default to deny, or user-prompt fallback, when LLM call fails?

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
| 2026-02-02 | Added hook migration testing decisions (record/replay fixtures, differential tests, snapshot tooling) |
| 2026-02-01 | Clarified no-daemon enforcement and policy-based self-improvement records |
| 2026-02-02 | Added hook parity testing details (normalization rules, fixture format, differential vs snapshot strategy) |
| 2026-02-03 | Added layered config/memory system design (global + project separation, tool shims, fallback resolution) |
| 2026-02-03 | Added open questions about simplifying global/local memory and hook versioning |
| 2026-02-04 | Added decision to avoid relative fallbacks when HOME is missing and to return Result for default_path |
| 2026-02-04 | Recorded PermissionRequest auto-approval triage direction and follow-up TODO/Open Question items |

# Memory System Analysis Report

**Generated**: 2026-02-04
**Project**: minions
**Memory Location**: `/Users/takuya/minions/.claude/memory/sessions/`

---

## Executive Summary

✅ **Status**: Memory system is operating normally with no critical issues detected.

### Key Findings

1. **251 session files** with 251 total events (1 event per session average)
2. **Single project only** - No cross-project contamination detected
3. **All observations** - Currently only recording tool observations
4. **Recent activity** - Active sessions on Feb 2-3, 2026

### Concerns

⚠️ **Limited memory diversity**: Only `observation` type recorded (no `preference`, `workflow`, `decision`, `error`)
⚠️ **Fixed importance score**: All events have identical score of 0.635
⚠️ **No user preferences captured**: System not yet learning from user corrections

---

## Basic Statistics

| Metric | Value |
|--------|-------|
| Total session files | 251 |
| Total events | 251 |
| Events per session | 1.0 |
| Date range | 2026-02-02 to 2026-02-03 |
| Active sessions (Feb 3) | 147 |
| Active sessions (Feb 2) | 104 |

---

## Memory Type Distribution

| Type | Count | Percentage |
|------|-------|------------|
| `observation` | 251 | 100.0% |

**Analysis**: Currently only capturing tool observations. Need to implement:
- `preference` - User preferences and corrections
- `workflow` - Recurring workflow patterns
- `decision` - Design decisions
- `error` - Error patterns and solutions

---

## Scope Distribution

| Scope | Count | Percentage |
|-------|-------|------------|
| `session` | 251 | 100.0% |

**Analysis**: All memories are session-scoped. Consider implementing:
- `project` - Project-wide memories
- `global` - Cross-project patterns

---

## Agent Distribution

| Agent | Count | Percentage |
|-------|-------|------------|
| `claude` | 251 | 100.0% |

**Analysis**: All events from main Claude agent. Subagent memories not yet captured.

---

## Context Distribution (Tool Usage)

| Context | Count | Percentage |
|---------|-------|------------|
| `tool:Bash` | 149 | 59.4% |
| `tool:Task` | 60 | 23.9% |
| `tool:Edit` | 31 | 12.4% |
| `tool:Write` | 11 | 4.4% |

**Analysis**:
- Primary tool: `Bash` (59.4%) - mostly git operations
- Delegation: `Task` (23.9%) - subagent spawning
- File ops: `Edit` + `Write` (16.8%)

---

## Bash Command Analysis

Top commands executed:

| Command | Count | Purpose |
|---------|-------|---------|
| `git` | 24 | Version control operations |
| `gh` | 13 | GitHub CLI operations (PR, issues) |
| `ls` | 8 | Directory listing |
| `echo` | 6 | Output/file writing |
| `cat` | 4 | File reading |
| `codex` | 4 | Codex CLI consultation |
| `uv` | 1 | Package management |
| `chmod` | 1 | Permission changes |
| `mkdir` | 1 | Directory creation |

**Insights**:
- Heavy git usage (24 + 13 = 37 git-related commands, ~25%)
- Codex consultation present but infrequent (4 calls)
- Gemini consultation not detected in recent sessions

---

## Task Tool Usage (Subagent Delegation)

Total Task calls: **60** (23.9% of all tool usage)

All Task calls follow hierarchy pattern:
```
Task (general-purpose): ## Hierarchy Context
Parent: conductor
Role: musician
```

**Analysis**: Proper Conductor → Musician delegation is occurring.

---

## Importance Score Statistics

| Metric | Value |
|--------|-------|
| Average score | 0.635 |
| Minimum score | 0.635 |
| Maximum score | 0.635 |

⚠️ **Issue**: All events have identical importance score. This suggests:
1. Scoring algorithm not differentiating event types
2. No dynamic importance calculation based on context
3. Potential for future improvement in relevance ranking

---

## Project Contamination Analysis

✅ **No contamination detected**

| Project | Mentions |
|---------|----------|
| `minions` | 33 |

**Conclusion**: Memory is correctly isolated to single project (`minions`). No cross-project leakage.

---

## Sample Content Analysis

### Typical Observation Format

```json
{
  "id": "20260203015711817859",
  "content": "Tool: Bash\nCommand: git status -> Success",
  "memory_type": "observation",
  "scope": "session",
  "source_agent": "claude",
  "context": "tool:Bash",
  "confidence": 1.0,
  "ttl_days": null,
  "tags": [],
  "metadata": {
    "tool_name": "Bash",
    "outcome": "success",
    "execution_time_ms": null,
    "command": "git status",
    "importance_score": 0.635
  },
  "created_at": "2026-02-03T01:57:11.817863"
}
```

---

## Recommendations

### 1. Implement Auto-Learning Hook ✓ Already Planned

`.claude/hooks/auto-learn.py` should capture:
- User corrections ("〜にして", "〜に変えて")
- Workflow patterns ("いつも〜", "毎回〜")
- Explicit memory requests ("/remember")

### 2. Diversify Memory Types

Currently 100% `observation`. Need to add:
```python
# preference
"PRは日本語で書く"

# workflow
"テスト → lint → コミット の順で実行"

# decision
"Rustフックを採用（パフォーマンス理由）"

# error
"uv sync失敗時は venv 削除して再作成"
```

### 3. Improve Importance Scoring

Current: All events = 0.635

Proposed:
```python
IMPORTANCE_WEIGHTS = {
    "preference": 0.9,     # High - directly affects behavior
    "workflow": 0.8,       # High - recurring patterns
    "decision": 0.85,      # High - architectural choices
    "error": 0.7,          # Medium - situational
    "observation": 0.5,    # Low - routine actions
}
```

### 4. Implement Memory Search

Enable CLI: `uv run python -m minions.memory.cli search <keyword>`

Should search:
- Content (full-text)
- Tags
- Context
- Weighted by importance score

### 5. Add Scope Levels

Current: Only `session`

Proposed:
- `session` - Current session only
- `project` - Project-wide (persists across sessions)
- `global` - Cross-project patterns

### 6. Capture Subagent Memories

Currently all from `source_agent: claude`.

Should also capture:
- Subagent decisions
- Codex recommendations
- Gemini research findings

---

## Current Project Info

```
Working Directory: /Users/takuya/minions
Git Remote: git@github.com:gyumaruya/minions.git
Total Session Files: 251
```

---

## Next Steps

1. ✅ Verify auto-learning hook is active
2. ⬜ Test user correction capture
3. ⬜ Implement dynamic importance scoring
4. ⬜ Add memory search functionality
5. ⬜ Expand scope beyond `session`
6. ⬜ Capture subagent memories

---

**Report End**

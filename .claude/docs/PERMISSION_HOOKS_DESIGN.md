# Permission Hooks Design Document

権限関連フックの設計ドキュメント。エージェント階層システムにおける権限管理を実装する。

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Permission Hooks                          │
├─────────────────────────────────────────────────────────────┤
│  enforce-hierarchy      │ Conductor の直接編集をブロック     │
│  enforce-delegation     │ 委譲なし連続作業を警告/ブロック    │
│  hierarchy-permissions  │ 権限継承を通知                     │
└─────────────────────────────────────────────────────────────┘
```

## Hooks Summary

| Hook | Event | Purpose | Action |
|------|-------|---------|--------|
| `enforce-hierarchy` | PreToolUse | Conductor の直接実装を禁止 | DENY |
| `enforce-delegation` | PreToolUse | 委譲なし連続作業を制限 | WARN → DENY |
| `hierarchy-permissions` | PostToolUse | 権限継承の通知 | INFO |

---

## 1. enforce-hierarchy

### Purpose

Conductor（指揮者）がコードファイルを直接編集することを防ぎ、Musician への委譲を強制する。

### Trigger Conditions

| Condition | Value |
|-----------|-------|
| Event Type | `PreToolUse` |
| Tool Matcher | `Edit`, `Write` |
| Agent Role | `AGENT_ROLE=conductor` |
| File Type | 実装ファイル（許可リスト外） |

### Decision Logic

```
IF tool_name NOT IN [Edit, Write] → ALLOW (skip)
IF file_path IN allowed_files → ALLOW
IF AGENT_ROLE == "musician" → ALLOW
IF AGENT_ROLE == "conductor" → DENY
ELSE → ALLOW (default: musician)
```

### Allowed Files (Conductor Can Edit)

| Pattern | Examples |
|---------|----------|
| `.claude/**` | `.claude/rules/*.md`, `.claude/settings.json` |
| `memory/**` | `memory/events.jsonl` |
| `pyproject.toml` | Root config |
| `settings.json` | Any settings file |
| `.gitignore` | Git ignore rules |

### Blocked Files (Must Delegate)

| Pattern | Examples |
|---------|----------|
| `src/**` | `src/main.rs`, `src/lib.py` |
| `lib/**` | `lib/utils.py` |
| `tests/**` | `tests/test_*.py` |
| Any implementation file | `*.rs`, `*.py`, `*.ts` |

---

## 2. enforce-delegation

### Purpose

Conductor が委譲なしで連続して作業ツールを使用した場合に警告・ブロックし、Musician への委譲を促す。

### Trigger Conditions

| Condition | Value |
|-----------|-------|
| Event Type | `PreToolUse` |
| Tool Matcher | Work tools (see below) |
| Agent Role | `AGENT_ROLE=conductor` |
| State | Sliding window tracking |

### Work Tools (Tracked)

| Tool | Description |
|------|-------------|
| `Edit` | File editing |
| `Write` | File creation |
| `Bash` | Command execution |
| `WebFetch` | Web requests |
| `WebSearch` | Web search |

### Warning/Block Thresholds

| Count | Action | Message |
|-------|--------|---------|
| 1-2 | ALLOW | (none) |
| 3-4 | WARN | ⚠ 委譲リマインダー: 3回連続で作業ツールを使用しています |
| 5+ | DENY | ⛔ 委譲が必要: Task ツールで Musician に委譲してください |

### State Management

| Parameter | Value |
|-----------|-------|
| State File | `.claude/.delegation-state.json` |
| Window Duration | 10 minutes |
| Reset Trigger | Task tool with `subagent_type` |

### State File Format

```json
{
  "work_tool_timestamps": [
    1706900000,
    1706900060,
    1706900120
  ]
}
```

### Reset Conditions

| Condition | Effect |
|-----------|--------|
| Task tool invoked | Counter reset |
| 10 minutes elapsed | Old entries pruned |
| Session restart | Counter reset |

### Allowed Files (Not Counted)

Same as enforce-hierarchy:
- `.claude/**`
- `memory/**`
- `pyproject.toml`
- `settings.json`
- `.gitignore`

---

## 3. hierarchy-permissions

### Purpose

Conductor が Task ツールで Musician を spawn した際に、継承される権限を通知する。

### Trigger Conditions

| Condition | Value |
|-----------|-------|
| Event Type | `PostToolUse` |
| Tool Matcher | `Task` |
| Subagent Type | Any |

### Permission Inheritance

#### Conductor → Musician

| Permission | Scope | Description |
|------------|-------|-------------|
| `Read` | `*` | All file read |
| `Edit` | `*` | All file edit |
| `Write` | `*` | All file write |
| `Glob` | `*` | File pattern search |
| `Grep` | `*` | Content search |
| `Bash` | `*` | Command execution |
| `Task` | `*` | Subagent spawn |
| `WebFetch` | `*` | Web fetch |
| `WebSearch` | `*` | Web search |

**Total: 9 permissions**

#### Musician (No Delegation)

Musician は最下層エージェントであり、Task ツールでサブエージェントを spawn できない。

---

## Permission Groups Summary

### By Role

| Role | Can Edit Code | Can Delegate | Permission Count |
|------|---------------|--------------|------------------|
| Conductor | ❌ (via hooks) | ✅ to Musician | 9 (full) |
| Musician | ✅ | ❌ | 9 (inherited) |

### By Tool

| Tool | Conductor | Musician |
|------|-----------|----------|
| Read | ✅ | ✅ |
| Edit | ⚠ (config only) | ✅ |
| Write | ⚠ (config only) | ✅ |
| Glob | ✅ | ✅ |
| Grep | ✅ | ✅ |
| Bash | ⚠ (tracked) | ✅ |
| Task | ✅ | ❌ |
| WebFetch | ⚠ (tracked) | ✅ |
| WebSearch | ⚠ (tracked) | ✅ |

**Legend:**
- ✅ = Allowed
- ❌ = Blocked
- ⚠ = Conditionally allowed (tracked or restricted)

---

## Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `AGENT_ROLE` | `conductor`, `musician` | `musician` | Current agent role |
| `AGENT_DISABLED` | `true`, `false` | `false` | Disable all agent hooks |

---

## Hook Execution Flow

```
User Request
     │
     ▼
┌─────────────────┐
│  PreToolUse     │
│  (Edit/Write)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ enforce-hierarchy│────▶│ DENY if Conductor│
│                 │     │ edits code       │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│enforce-delegation│────▶│ WARN at 3       │
│                 │     │ DENY at 5       │
└────────┬────────┘     └─────────────────┘
         │
         ▼
    Tool Executes
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  PostToolUse    │────▶│ Report inherited │
│  (Task)         │     │ permissions      │
└─────────────────┘     └─────────────────┘
```

---

---

## Permission Configuration (settings.json)

### Allow List (Whitelist)

```json
{
  "permissions": {
    "allow": [
      "Read(*)",
      "Edit(*)",
      "Write(*)",
      "MultiEdit(*)",
      "Glob(*)",
      "Grep(*)",
      "LS(*)",
      "WebFetch(*)",
      "WebSearch(*)",
      "Task(*)",
      "Skill(*)",
      "TodoRead(*)",
      "TodoWrite(*)",
      "Bash(*)"
    ]
  }
}
```

**設計方針:** `Bash(*)` で全コマンドを許可し、危険なコマンドのみ deny リストでブロック。

### Deny List (Blocklist)

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./**/*.pem)",
      "Read(./**/*.key)",
      "Read(./**/credentials*)",
      "Read(./**/*secret*)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Read(~/.config/gcloud/**)",
      "Bash(rm -rf /)",
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~)",
      "Bash(rm -rf ~/*)",
      "Bash(sudo rm -rf *)"
    ]
  }
}
```

### Subagent Permission Inheritance

| 親 | 子 | 権限継承 |
|----|----|----|
| Conductor | Musician | 全権限を継承（settings.json の allow/deny が適用） |
| Musician | N/A | サブエージェント spawn 不可 |

**重要:** サブエージェントは親の権限を自動継承するため、`Bash(*)` を許可リストに追加することで「Bash ~~ denied」エラーを解消。

---

## Design Gaps / Future Improvements

### Current Limitations

1. **Section Leader 未実装**
   - 現在は 2 層（Conductor → Musician）のみ
   - Section Leader（John von Neumann）は将来の拡張オプション

2. **Permission Granularity**
   - 現在は `*`（全許可）のみ
   - ファイルパターン別の細かい権限制御なし

3. **Cross-Session State**
   - delegation state は `/tmp/claude-delegation-*.json` に保存
   - セッション間での状態継続あり（10分ウィンドウ）

4. **Rust Hooks 未統合**
   - hooks-rs/ に Rust 実装があるが、settings.json はまだ Python フックを参照
   - Python フックは `main()` がコメントアウトされている状態

### Potential Enhancements

| Feature | Description | Priority |
|---------|-------------|----------|
| Path-based permissions | `/src/**` vs `/tests/**` 別権限 | Medium |
| Command-specific Bash | `git:*`, `npm:*` 別権限 | Low |
| 3-tier hierarchy | Section Leader 追加 | Low |
| Audit logging | 権限チェック結果のログ | Medium |
| Dynamic thresholds | プロジェクト別の閾値設定 | Low |

---

---

## Debug Mode

権限フックの動作をデバッグするためのログ機能。

### 有効化方法

```bash
# スクリプトで有効化
.claude/scripts/hook-debug.sh enable

# または環境変数
export CLAUDE_HOOK_DEBUG=1

# またはマーカーファイル作成
touch .claude/.hook-debug
```

### ログ出力先

```
.claude/logs/hook-debug.jsonl
```

### ログフォーマット

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "hook_name": "enforce-hierarchy",
  "tool_name": "Edit",
  "tool_input_summary": "file_path: src/main.rs",
  "agent_role": "conductor",
  "decision": "deny",
  "reason": "Conductor cannot edit implementation files"
}
```

### デバッグコマンド

```bash
# ステータス確認
.claude/scripts/hook-debug.sh status

# リアルタイム監視
.claude/scripts/hook-debug.sh tail

# 直近50件を表示
.claude/scripts/hook-debug.sh view

# ログクリア
.claude/scripts/hook-debug.sh clear

# 無効化
.claude/scripts/hook-debug.sh disable
```

### Decision Types

| Decision | 意味 |
|----------|------|
| `allow` | 許可（明示的） |
| `deny` | 拒否 |
| `warn` | 警告付き許可 |
| `skip` | チェック対象外 |
| `reset` | カウンターリセット |
| `delegation` | 委譲検出 |

---

## Related Documents

- `.claude/rules/agent-hierarchy.md` - Agent hierarchy rules
- `hooks-rs/README.md` - Rust hooks overview
- `.claude/agents/instructions/conductor.md` - Conductor instructions
- `.claude/agents/instructions/musician.md` - Musician instructions

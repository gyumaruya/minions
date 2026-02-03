# hooks-rs: Rust Hooks for Claude Code

Cross-platform Rust implementation of Claude Code hooks. Replaces Python hooks for better reliability across Mac, Linux, and Windows.

## Benefits over Python hooks

- **No Python dependency** - Single binary, no virtualenv needed
- **No syntax errors** - Compiled language catches errors at build time
- **Cross-platform** - Same binary works on Mac, Linux, Windows
- **Fast startup** - No interpreter overhead

## Structure

```
hooks-rs/
├── crates/
│   ├── hook-common/       # Shared library for all hooks
│   │   ├── input.rs       # JSON stdin parsing (HookInput)
│   │   ├── output.rs      # JSON stdout output (HookOutput)
│   │   ├── state.rs       # State file management
│   │   └── subprocess.rs  # Command execution helpers
│   │
│   ├── hook-memory/       # Memory system for self-improvement
│   │   ├── schema.rs      # MemoryEvent, MemoryType, etc.
│   │   └── storage.rs     # JSONL storage
│   │
│   └── hooks/             # Individual hook binaries
│       ├── enforce-no-merge/       # Block git merge commands
│       ├── enforce-draft-pr/       # Ensure PRs are draft
│       ├── prevent-secrets-commit/ # Block secrets in commits
│       ├── ensure-pr-open/         # Require open PR for edits
│       ├── enforce-japanese/       # Enforce Japanese in PRs
│       ├── lint-on-save/           # Run ruff/ty on Python files
│       ├── log-cli-tools/          # Log Codex/Gemini usage
│       ├── ensure-noreply-email/   # Set noreply git email
│       ├── auto-create-pr/         # Auto-create PR at session start
│       ├── enforce-delegation/     # Enforce Conductor delegation
│       ├── auto-commit-on-verify/  # Auto-push after tests pass
│       ├── agent-router/           # Route to Codex/Gemini/Copilot
│       ├── enforce-hierarchy/      # Enforce agent hierarchy
│       ├── hierarchy-permissions/  # Permission inheritance
│       ├── post-test-analysis/     # Suggest Codex for failures
│       ├── check-codex-before-write/ # Suggest Codex for design
│       ├── check-codex-after-plan/ # Suggest Codex plan review
│       ├── suggest-gemini-research/ # Suggest Gemini for research
│       ├── post-implementation-review/ # Suggest review after edits
│       ├── load-memories/          # Load memories at session start
│       ├── auto-learn/             # Learn from user corrections
│       ├── pre-tool-recall/        # Recall memories before tools
│       └── post-tool-record/       # Record tool executions
```

## Hook Categories

### Tier 1: Core Blocking Hooks
- `enforce-no-merge` - Blocks `git merge` and `gh pr merge`
- `enforce-draft-pr` - Ensures `gh pr create` uses `--draft`
- `prevent-secrets-commit` - Blocks commits containing secrets
- `ensure-pr-open` - Blocks Edit/Write without open PR

### Tier 2: Workflow Hooks
- `enforce-japanese` - Enforces Japanese in PR/commit messages
- `lint-on-save` - Runs ruff format/check and ty on Python files
- `log-cli-tools` - Logs Codex/Gemini CLI usage to JSONL
- `ensure-noreply-email` - Sets git email to noreply before commits
- `auto-create-pr` - Creates feature branch and draft PR at session start
- `enforce-delegation` - Reminds Conductor to delegate to Musicians
- `auto-commit-on-verify` - Suggests push after successful tests
- `agent-router` - Routes tasks to appropriate agent (Codex/Gemini/Copilot)

### Tier 3: Hierarchy Hooks
- `enforce-hierarchy` - Blocks direct edits by Conductor/Section Leader
- `hierarchy-permissions` - Notifies about permission inheritance

### Tier 4: Suggestion Hooks
- `post-test-analysis` - Suggests Codex after test failures
- `check-codex-before-write` - Suggests Codex for design files
- `check-codex-after-plan` - Suggests Codex plan review
- `suggest-gemini-research` - Suggests Gemini for research tasks
- `post-implementation-review` - Suggests review after many edits

### Tier 5: Memory Hooks
- `load-memories` - Loads relevant memories at session start
- `auto-learn` - Learns from user corrections (〜にして, 毎回〜, etc.)
- `pre-tool-recall` - Recalls relevant memories before tool execution
- `post-tool-record` - Records tool executions to memory

## Building

```bash
cd hooks-rs
cargo build --release
```

Binaries are output to `target/release/`.

## Testing

```bash
cargo test --release
```

## Usage

Configure in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks-rs/target/release/enforce-no-merge",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

## Hook Protocol

Hooks receive JSON on stdin and output JSON to stdout.

### Input (stdin)
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git status"
  },
  "tool_output": "...",
  "user_prompt": "..."
}
```

### Output (stdout)
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "additionalContext": "Message to show",
    "blockingError": "Error message (blocks operation)"
  }
}
```

## Development

### Adding a new hook

1. Create directory: `mkdir -p crates/hooks/my-hook/src`
2. Add `Cargo.toml` with `hook-common` dependency
3. Implement `main.rs` using `HookInput::from_stdin()` and `HookOutput`
4. Add to workspace `Cargo.toml` members
5. Build and test

### Common patterns

```rust
use hook_common::prelude::*;

fn main() -> anyhow::Result<()> {
    let input = HookInput::from_stdin()?;

    // Check tool type
    if !input.is_bash() {
        return Ok(());
    }

    // Get command
    let command = input.get_command().unwrap_or("");

    // Allow with context
    let output = HookOutput::allow().with_context("Info message");
    output.write_stdout()?;

    // Or deny
    let output = HookOutput::deny().with_context("Reason for denial");
    output.write_stdout()?;

    Ok(())
}
```

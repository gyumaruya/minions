//! PostToolUse hook: Auto-push after successful verification when PR is open.
//!
//! Triggers when test/verification commands pass and suggests auto-push.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::run_command_with_timeout;
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(10);

// Commands that indicate successful verification
const VERIFICATION_COMMANDS: &[&str] = &[
    "pytest",
    "npm test",
    "npm run test",
    "uv run pytest",
    "poe test",
    "poe all",
    "ruff check",
    "ty check",
];

// Commands that indicate successful agent verification
const AGENT_VERIFICATION_PATTERNS: &[&str] = &["copilot -p", "codex exec", "gemini -p"];

// Output patterns indicating failure
const FAILURE_PATTERNS: &[&str] = &["failed", "error", "❌", "FAILED", "ERROR"];

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only process Bash commands
    if !input.is_bash() {
        return Ok(());
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()),
    };

    // Check if this is a verification command
    if !is_verification_command(command) {
        return Ok(());
    }

    // Get tool output and check if successful
    let output = input.tool_output.as_deref().unwrap_or("");

    // For PostToolUse, we need to check success
    if !is_successful(output) {
        return Ok(());
    }

    // Check if there are uncommitted changes
    if !has_uncommitted_changes() {
        return Ok(());
    }

    // Check if PR is open
    let context = if has_open_pr() {
        "[Auto-Push] PR is open. Verification passed with uncommitted changes. \
         Push automatically: `git add -A && git commit -m \"...\" && git push`"
            .to_string()
    } else {
        "[PR Required] No open PR. Create feature branch and PR first: \
         `git push -u origin <branch> && gh pr create --draft`"
            .to_string()
    };

    let output = HookOutput::post_tool_use().with_context(context);
    output.write_stdout()?;

    Ok(())
}

fn is_verification_command(command: &str) -> bool {
    let cmd_lower = command.to_lowercase();

    for vc in VERIFICATION_COMMANDS {
        if cmd_lower.contains(vc) {
            return true;
        }
    }

    for pattern in AGENT_VERIFICATION_PATTERNS {
        if cmd_lower.contains(pattern) {
            return true;
        }
    }

    false
}

fn is_successful(output: &str) -> bool {
    let output_lower = output.to_lowercase();

    // Check for failure patterns
    for pattern in FAILURE_PATTERNS {
        if output_lower.contains(&pattern.to_lowercase()) {
            return false;
        }
    }

    true
}

fn has_uncommitted_changes() -> bool {
    run_command_with_timeout("git status --porcelain", TIMEOUT)
        .map(|r| !r.stdout.trim().is_empty())
        .unwrap_or(false)
}

fn has_open_pr() -> bool {
    run_command_with_timeout(
        "gh pr list --state open --json number --limit 1",
        TIMEOUT,
    )
    .map(|r| {
        r.success
            && r.stdout.contains('[')
            && !r.stdout.contains("[]")
    })
    .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_verification_command() {
        assert!(is_verification_command("uv run pytest"));
        assert!(is_verification_command("npm test"));
        assert!(is_verification_command("poe test"));
        assert!(!is_verification_command("git status"));
        assert!(!is_verification_command("ls -la"));
    }

    #[test]
    fn test_is_successful() {
        assert!(is_successful("All tests passed"));
        assert!(!is_successful("FAILED: test_example"));
        assert!(!is_successful("Error: something wrong"));
    }
}

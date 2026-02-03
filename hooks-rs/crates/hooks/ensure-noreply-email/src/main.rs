//! PreToolUse hook: Ensure noreply email is used for git commits.
//!
//! Sets git email to noreply before commit/push operations.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::run_command_with_timeout;
use std::time::Duration;

const NOREPLY_EMAIL: &str = "gyumaruya@users.noreply.github.com";
const TIMEOUT: Duration = Duration::from_secs(2);

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

    // Check if it's a git command that might commit
    let is_git_commit = command.starts_with("git ")
        && (command.contains("commit") || command.contains("push"));

    if !is_git_commit {
        return Ok(());
    }

    // Get current email
    let current_email = get_current_email();

    // Set email if missing or different from noreply
    if current_email.as_ref() != Some(&NOREPLY_EMAIL.to_string()) {
        set_email();
    }

    // Allow the command
    Ok(())
}

fn get_current_email() -> Option<String> {
    let result = run_command_with_timeout("git config user.email", TIMEOUT).ok()?;
    if result.success {
        Some(result.stdout.trim().to_string())
    } else {
        None
    }
}

fn set_email() {
    let cmd = format!("git config user.email {}", NOREPLY_EMAIL);
    let _ = run_command_with_timeout(&cmd, TIMEOUT);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_noreply_email_constant() {
        assert!(NOREPLY_EMAIL.contains("noreply.github.com"));
    }
}

//! Ensure PR is open before allowing Edit/Write.
//!
//! If no open PR exists, attempts to create one automatically.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::{gh, git, run_command_with_timeout};
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(30);

const WARN_MESSAGE: &str = r#"⚠️ PRを作成できませんでした。

次回の git push で自動的にPRが作成されます。
または手動で作成してください:
1. git push -u origin <branch-name>
2. gh pr create --draft --title "WIP: ..." --body "..."
"#;

/// Check if there's an open PR for the current branch.
fn has_any_open_pr() -> bool {
    // Get current branch
    let branch_result = match git("branch --show-current") {
        Ok(r) if r.success => r,
        _ => return false,
    };
    let branch = branch_result.stdout.trim();

    // Check for PR on current branch
    let cmd = format!("pr list --state open --head {} --json number", branch);
    match gh(&cmd) {
        Ok(result) if result.success => {
            // Parse JSON array
            if let Ok(prs) = serde_json::from_str::<Vec<serde_json::Value>>(&result.stdout) {
                !prs.is_empty()
            } else {
                false
            }
        }
        _ => false,
    }
}

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Early return if not a git repository
    if !is_git_repo() {
        return Ok(());
    }

    // Only check Edit and Write tools
    if !input.is_edit() && !input.is_write() {
        return Ok(());
    }

    // Check if any PR is open
    if has_any_open_pr() {
        return Ok(());
    }

    // No PR open - try to create one
    match create_pr_if_possible() {
        Ok(()) => {
            // Successfully created PR
            return Ok(());
        }
        Err(_) => {
            // Failed to create PR - block the operation
            let output = HookOutput::deny().with_blocking_error(WARN_MESSAGE);
            output.write_stdout()?;
            return Ok(());
        }
    }
}

/// Attempt to create a PR if branch is not yet pushed.
fn create_pr_if_possible() -> Result<()> {
    // Get current branch
    let branch_result = git("branch --show-current")?;
    if !branch_result.success {
        anyhow::bail!("Failed to get current branch");
    }
    let branch = branch_result.stdout.trim();

    // Validate branch name (alphanumeric, hyphen, underscore, slash only)
    if !branch.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '_' || c == '/') {
        anyhow::bail!("Invalid branch name contains special characters");
    }

    // Don't create PR for main branch
    if branch == "main" || branch == "master" {
        anyhow::bail!("Cannot create PR from main branch");
    }

    // Try to push the branch
    let push_cmd = format!("git push -u origin {}", branch);
    let push_result = run_command_with_timeout(&push_cmd, TIMEOUT)?;

    if !push_result.success {
        // Push failed - maybe branch doesn't exist remotely yet
        // User needs to make commits first
        anyhow::bail!("Push failed: {}", push_result.stderr);
    }

    // Branch is now pushed - try to create PR
    let pr_cmd = format!(
        "gh pr create --draft --title 'WIP: {}' --body '🤖 Auto-created by Claude Code'",
        branch
    );
    let pr_result = run_command_with_timeout(&pr_cmd, TIMEOUT)?;

    if !pr_result.success {
        anyhow::bail!("PR creation failed: {}", pr_result.stderr);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_has_open_pr_returns_bool() {
        // Just verify the function doesn't panic
        let _ = has_any_open_pr();
    }
}

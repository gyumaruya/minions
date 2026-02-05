//! PostToolUse hook: Auto-create PR after successful git push.
//!
//! Monitors git push operations and creates a draft PR if none exists.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::{gh, git, run_command_with_timeout};
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(30);

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Early return if not a git repository
    if !is_git_repo() {
        return Ok(());
    }

    // Only process Bash tool
    if !input.is_bash() {
        return Ok(());
    }

    // Check if command was git push
    let command = input.tool_input.command.as_deref().unwrap_or("");

    if !command.contains("git push") {
        return Ok(());
    }

    // Check if push was successful
    let output_success = input.tool_output
        .as_ref()
        .and_then(|json_str| serde_json::from_str::<serde_json::Value>(json_str).ok())
        .and_then(|v| v.get("result")?.get("success")?.as_bool())
        .unwrap_or(false);

    if !output_success {
        return Ok(());
    }

    // Check if PR already exists
    if has_any_open_pr() {
        return Ok(());
    }

    // Try to create PR
    match create_pr() {
        Ok(pr_url) => {
            let context = format!("✅ PRを自動作成しました: {}", pr_url);
            let output = HookOutput::post_tool_use().with_context(context);
            output.write_stdout()?;
        }
        Err(e) => {
            let context = format!("⚠️ PR自動作成に失敗: {}", e);
            let output = HookOutput::post_tool_use().with_context(context);
            output.write_stdout()?;
        }
    }

    Ok(())
}

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
            if let Ok(prs) = serde_json::from_str::<Vec<serde_json::Value>>(&result.stdout) {
                !prs.is_empty()
            } else {
                false
            }
        }
        _ => false,
    }
}

/// Create a draft PR for the current branch.
fn create_pr() -> Result<String> {
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

    // Create draft PR
    let pr_cmd = format!(
        "gh pr create --draft --title 'WIP: {}' --body '🤖 Auto-created by Claude Code after git push'",
        branch
    );
    let pr_result = run_command_with_timeout(&pr_cmd, TIMEOUT)?;

    if !pr_result.success {
        anyhow::bail!("PR creation failed: {}", pr_result.stderr);
    }

    // Extract PR URL from output
    let pr_url = pr_result.stdout.lines()
        .find(|line| line.starts_with("https://"))
        .unwrap_or(&pr_result.stdout)
        .trim()
        .to_string();

    Ok(pr_url)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_has_open_pr_returns_bool() {
        let _ = has_any_open_pr();
    }
}

//! Enforce no merge hook.
//!
//! Blocks merge operations (gh pr merge, git merge).
//! Users should perform merges manually.

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;

const BLOCK_MESSAGE: &str = r#"⛔ マージ操作はブロックされています。

【理由】
マージはユーザーが行うべき操作です。

【許可されている操作】
- gh pr ready（レビュー準備完了にする）
- gh pr view（PRを確認する）

【マージ方法】
GitHub UI または以下のコマンドをユーザーが実行:
  gh pr merge <number>"#;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only check Bash commands
    if !input.is_bash() {
        return Ok(()); // Silent pass for non-Bash tools
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()), // No command, pass
    };

    // Check for merge commands
    if is_merge_command(command) {
        let output = HookOutput::deny()
            .with_context(BLOCK_MESSAGE);
        output.write_stdout()?;
    }

    // Silent pass for allowed commands
    Ok(())
}

/// Check if command is a merge operation.
fn is_merge_command(command: &str) -> bool {
    // gh pr merge
    let gh_merge = Regex::new(r"\bgh\s+pr\s+merge\b").unwrap();
    if gh_merge.is_match(command) {
        return true;
    }

    // git merge (but not in commit message context)
    let git_merge = Regex::new(r"\bgit\s+merge\b").unwrap();
    if git_merge.is_match(command) {
        // Allow if it's clearly a commit message or echo
        if command.contains("echo") || command.contains("-m \"") || command.contains("-m '") {
            return false;
        }
        return true;
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gh_pr_merge_blocked() {
        assert!(is_merge_command("gh pr merge 123"));
        assert!(is_merge_command("gh pr merge"));
        assert!(is_merge_command("  gh  pr  merge  --auto"));
    }

    #[test]
    fn test_git_merge_blocked() {
        assert!(is_merge_command("git merge main"));
        assert!(is_merge_command("git merge feature/branch"));
    }

    #[test]
    fn test_allowed_commands() {
        assert!(!is_merge_command("gh pr ready"));
        assert!(!is_merge_command("gh pr view"));
        assert!(!is_merge_command("git status"));
        assert!(!is_merge_command("git commit -m \"Merge changes\""));
    }
}

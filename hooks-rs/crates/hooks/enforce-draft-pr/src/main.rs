//! Enforce draft PR workflow hook.
//!
//! - Blocks PR creation without --draft flag
//! - Requires confirmation for gh pr ready

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;

const BLOCK_NON_DRAFT: &str = r#"⚠️ PR は必ず --draft で作成してください。

修正: gh pr create --draft ...

理由: レビュー準備が整うまで draft 状態を維持するルールです。"#;

const ASK_PR_READY: &str = r#"⚠️ PR を ready にしようとしています。

本当にレビュー準備が完了していますか？

- まだ編集が必要な場合: このコマンドをスキップしてください
- 準備完了の場合: ユーザーが明示的に許可してください

/pr-workflow ready を使用するか、手動で gh pr ready を実行してください。"#;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only check Bash commands
    if !input.is_bash() {
        return Ok(());
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()),
    };

    // Check gh pr create without --draft
    let pr_create = Regex::new(r"\bgh\s+pr\s+create\b").unwrap();
    if pr_create.is_match(command) {
        if !command.contains("--draft") {
            let output = HookOutput::deny().with_context(BLOCK_NON_DRAFT);
            output.write_stdout()?;
        }
        return Ok(());
    }

    // Check gh pr ready - requires confirmation
    let pr_ready = Regex::new(r"\bgh\s+pr\s+ready\b").unwrap();
    if pr_ready.is_match(command) {
        // Check for bypass environment variable
        if std::env::var("ALLOW_PR_READY").map_or(false, |v| v == "1") {
            return Ok(());
        }
        let output = HookOutput::ask().with_context(ASK_PR_READY);
        output.write_stdout()?;
        return Ok(());
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pr_create_patterns() {
        let pr_create = Regex::new(r"\bgh\s+pr\s+create\b").unwrap();
        assert!(pr_create.is_match("gh pr create --title test"));
        assert!(pr_create.is_match("gh pr create --draft --title test"));
    }

    #[test]
    fn test_draft_detection() {
        let cmd = "gh pr create --draft --title test";
        assert!(cmd.contains("--draft"));

        let cmd = "gh pr create --title test";
        assert!(!cmd.contains("--draft"));
    }
}

//! Ensure PR is open before allowing Edit/Write.
//!
//! Blocks file modifications if no open PR exists.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::gh;

const BLOCK_MESSAGE: &str = r#"⛔ 編集をブロック: オープンなPRがありません。

セッション開始時に自動でPRが作成されるはずですが、作成に失敗した可能性があります。

手動で作成してください:
1. git push -u origin <branch-name>
2. gh pr create --draft --title "WIP: ..." --body "..."

または新しいセッションを開始してください。"#;

/// Check if there's any open PR for the current repository.
fn has_any_open_pr() -> bool {
    match gh("pr list --state open --json number") {
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

    // Only check Edit and Write tools
    if !input.is_edit() && !input.is_write() {
        return Ok(());
    }

    // Check if any PR is open
    if has_any_open_pr() {
        return Ok(());
    }

    // No PR open - block the operation
    let output = HookOutput::deny().with_blocking_error(BLOCK_MESSAGE);
    output.write_stdout()?;

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

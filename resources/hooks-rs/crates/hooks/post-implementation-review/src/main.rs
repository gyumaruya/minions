//! PostToolUse hook: Suggest Codex review after significant implementations.
//!
//! Tracks file changes and suggests code review when substantial
//! code has been written.

use anyhow::Result;
use hook_common::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

// State file to track changes in this session
fn state_file() -> PathBuf {
    PathBuf::from("/tmp/claude-code-implementation-state.json")
}

// Thresholds for suggesting review
const MIN_FILES_FOR_REVIEW: usize = 3;
const MIN_LINES_FOR_REVIEW: usize = 100;

// Source file extensions
const SOURCE_EXTENSIONS: &[&str] = &[".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs"];

#[derive(Serialize, Deserialize, Default)]
struct ImplementationState {
    files_changed: Vec<String>,
    total_lines: usize,
    review_suggested: bool,
}

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = &input.tool_name;

    // Only process Write/Edit tools
    if tool_name != "Write" && tool_name != "Edit" {
        return Ok(());
    }

    let file_path = input.get_file_path().unwrap_or("");
    let content = input.tool_input.content.as_deref().unwrap_or("");

    // Validate input
    if file_path.is_empty() || file_path.len() > 4096 || file_path.contains("..") {
        return Ok(());
    }

    // Skip non-source files
    if !SOURCE_EXTENSIONS.iter().any(|ext| file_path.ends_with(ext)) {
        return Ok(());
    }

    // Load and update state
    let mut state = load_state();

    if !state.files_changed.contains(&file_path.to_string()) {
        state.files_changed.push(file_path.to_string());
    }

    state.total_lines += count_lines(content);
    save_state(&state);

    // Check if review should be suggested
    if let Some(reason) = should_suggest_review(&state) {
        let mut updated_state = state;
        updated_state.review_suggested = true;
        save_state(&updated_state);

        let context = format!(
            "[Code Review Suggestion] {} in this session. \
             Consider having Codex review the implementation. \
             **Recommended**: Use Task tool with subagent_type='general-purpose' \
             to consult Codex with git diff and preserve main context.",
            reason
        );

        let output = HookOutput::post_tool_use().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn load_state() -> ImplementationState {
    fs::read_to_string(state_file())
        .ok()
        .and_then(|content| serde_json::from_str(&content).ok())
        .unwrap_or_default()
}

fn save_state(state: &ImplementationState) {
    if let Ok(content) = serde_json::to_string(state) {
        let _ = fs::write(state_file(), content);
    }
}

fn count_lines(content: &str) -> usize {
    content
        .lines()
        .filter(|line| {
            let trimmed = line.trim();
            !trimmed.is_empty() && !trimmed.starts_with('#') && !trimmed.starts_with("//")
        })
        .count()
}

fn should_suggest_review(state: &ImplementationState) -> Option<String> {
    if state.review_suggested {
        return None;
    }

    let files_count = state.files_changed.len();

    if files_count >= MIN_FILES_FOR_REVIEW {
        return Some(format!("{} files modified", files_count));
    }

    if state.total_lines >= MIN_LINES_FOR_REVIEW {
        return Some(format!("{}+ lines written", state.total_lines));
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_count_lines() {
        assert_eq!(count_lines("line1\nline2\n\n# comment"), 2);
        assert_eq!(count_lines("// comment\ncode\n"), 1);
    }

    #[test]
    fn test_should_suggest_review() {
        let state = ImplementationState {
            files_changed: vec!["a.py".into(), "b.py".into(), "c.py".into()],
            total_lines: 50,
            review_suggested: false,
        };
        assert!(should_suggest_review(&state).is_some());

        let state2 = ImplementationState {
            files_changed: vec!["a.py".into()],
            total_lines: 150,
            review_suggested: false,
        };
        assert!(should_suggest_review(&state2).is_some());
    }
}

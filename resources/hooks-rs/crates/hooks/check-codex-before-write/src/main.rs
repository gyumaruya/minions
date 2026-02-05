//! PreToolUse hook: Check if Codex consultation is recommended before Write/Edit.
//!
//! Analyzes the file being modified and suggests Codex consultation
//! for design decisions, complex implementations, or architectural changes.

use anyhow::Result;
use hook_common::prelude::*;

// Patterns that suggest design/architecture decisions
const DESIGN_INDICATORS: &[&str] = &[
    "DESIGN.md",
    "ARCHITECTURE.md",
    "architecture",
    "design",
    "schema",
    "model",
    "interface",
    "abstract",
    "base_",
    "core/",
    "/core/",
    "config",
    "settings",
    "class ",
    "interface ",
    "abstract class",
    "def __init__",
    "from abc import",
    "Protocol",
    "@dataclass",
    "TypedDict",
];

// Files that are typically simple edits
const SIMPLE_EDIT_PATTERNS: &[&str] = &[
    ".gitignore",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    ".env.example",
];

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = input.tool_name.as_str();

    // Only check Edit and Write tools
    if tool_name != "Edit" && tool_name != "Write" {
        return Ok(());
    }

    let file_path = input.get_file_path().unwrap_or("");
    let content = input.tool_input.content.as_deref().unwrap_or("");

    // Validate input
    if file_path.is_empty() || file_path.len() > 4096 || file_path.contains("..") {
        return Ok(());
    }

    if let Some(reason) = should_suggest_codex(file_path, content) {
        let context = format!(
            "[Codex Consultation Reminder] {}. \
             Consider consulting Codex before making this change. \
             **Recommended**: Use Task tool with subagent_type='general-purpose' \
             to preserve main context. \
             (Direct call OK for quick questions: \
             `codex exec --model gpt-5.2-codex --sandbox read-only --full-auto '...'`)",
            reason
        );

        let output = HookOutput::allow().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn should_suggest_codex(file_path: &str, content: &str) -> Option<String> {
    let filepath_lower = file_path.to_lowercase();

    // Skip simple edits
    for pattern in SIMPLE_EDIT_PATTERNS {
        if filepath_lower.contains(&pattern.to_lowercase()) {
            return None;
        }
    }

    // Check file path for design indicators
    for indicator in DESIGN_INDICATORS {
        if filepath_lower.contains(&indicator.to_lowercase()) {
            return Some(format!("File path contains '{}' - likely a design decision", indicator));
        }
    }

    // Check content if available
    if !content.is_empty() {
        // New file with significant content
        if content.len() > 500 {
            return Some("Creating new file with significant content".to_string());
        }

        // Check for design patterns in content
        for indicator in DESIGN_INDICATORS {
            if content.contains(indicator) {
                return Some(format!(
                    "Content contains '{}' - likely architectural code",
                    indicator
                ));
            }
        }
    }

    // New files in src/ directory
    if file_path.contains("/src/") || file_path.starts_with("src/") {
        if content.len() > 200 {
            return Some("New source file - consider design review".to_string());
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_should_suggest_codex() {
        // Design files
        assert!(should_suggest_codex("DESIGN.md", "").is_some());
        assert!(should_suggest_codex("src/core/base.py", "").is_some());

        // Simple files
        assert!(should_suggest_codex("README.md", "").is_none());
        assert!(should_suggest_codex(".gitignore", "").is_none());

        // Content with design patterns
        assert!(should_suggest_codex("file.py", "class MyClass:").is_some());
    }
}

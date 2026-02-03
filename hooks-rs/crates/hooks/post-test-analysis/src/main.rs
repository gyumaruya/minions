//! PostToolUse hook: Suggest Codex analysis after test/build failures.
//!
//! Analyzes test and build output and suggests Codex consultation
//! for debugging complex failures.

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;

// Commands that run tests or builds
const TEST_BUILD_COMMANDS: &[&str] = &[
    "pytest",
    "npm test",
    "npm run test",
    "npm run build",
    "uv run pytest",
    "ruff check",
    "ty check",
    "mypy",
    "tsc",
    "cargo test",
    "go test",
    "make test",
    "make build",
];

// Patterns indicating failures
const FAILURE_PATTERNS: &[&str] = &[
    "FAILED",
    "ERROR",
    r"error\[",
    "Error:",
    "failed",
    "error:",
    "AssertionError",
    "TypeError",
    "ValueError",
    "AttributeError",
    "ImportError",
    "ModuleNotFoundError",
    "SyntaxError",
    "Exception",
    "Traceback",
    "panic:",
    "FAIL:",
];

// Simple errors that don't need Codex
const SIMPLE_ERRORS: &[&str] = &[
    "ModuleNotFoundError",
    "command not found",
    "No such file or directory",
];

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only process Bash tool
    if !input.is_bash() {
        return Ok(());
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()),
    };

    // Check if it's a test/build command
    if !is_test_or_build_command(command) {
        return Ok(());
    }

    let tool_output = input.tool_output.as_deref().unwrap_or("");

    // Check for complex failures
    if let Some(reason) = has_complex_failure(tool_output) {
        let context = format!(
            "[Codex Debug Suggestion] {}. \
             Consider consulting Codex for debugging analysis. \
             **Recommended**: Use Task tool with subagent_type='general-purpose' \
             to consult Codex with full error context and preserve main context.",
            reason
        );

        let output = HookOutput::post_tool_use().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn is_test_or_build_command(command: &str) -> bool {
    let cmd_lower = command.to_lowercase();
    TEST_BUILD_COMMANDS
        .iter()
        .any(|cmd| cmd_lower.contains(cmd))
}

fn has_complex_failure(output: &str) -> Option<String> {
    // Skip if it's a simple error
    for simple in SIMPLE_ERRORS {
        if output.contains(simple) {
            return None;
        }
    }

    // Count failure patterns
    let mut failure_count = 0;

    for pattern in FAILURE_PATTERNS {
        if let Ok(re) = Regex::new(&format!("(?i){}", regex::escape(pattern))) {
            failure_count += re.find_iter(output).count();
        }
    }

    // Multiple failures suggest need for Codex
    if failure_count >= 3 {
        return Some(format!(
            "Multiple failures detected ({} issues)",
            failure_count
        ));
    }

    // Single failure with traceback
    let output_lower = output.to_lowercase();
    if failure_count >= 1
        && (output_lower.contains("traceback") || output_lower.contains("assertion"))
    {
        return Some("Test failure with traceback".to_string());
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_test_or_build_command() {
        assert!(is_test_or_build_command("uv run pytest"));
        assert!(is_test_or_build_command("cargo test"));
        assert!(!is_test_or_build_command("git status"));
    }

    #[test]
    fn test_has_complex_failure() {
        assert!(has_complex_failure("FAILED test1\nFAILED test2\nFAILED test3").is_some());
        assert!(has_complex_failure("Error: test failed\nTraceback...").is_some());
        assert!(has_complex_failure("All tests passed").is_none());
        assert!(has_complex_failure("ModuleNotFoundError: xyz").is_none());
    }
}

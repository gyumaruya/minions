//! PostToolUse hook: Record tool execution results to memory.
//!
//! Records tool executions (Bash, Edit, Write, etc.) for the
//! self-improvement memory cycle.

use anyhow::Result;
use hook_common::prelude::*;
use hook_memory::{AgentType, MemoryEvent, MemoryScope, MemoryStorage, MemoryType};

// Tools worth recording
const RECORDABLE_TOOLS: &[&str] = &["Bash", "Edit", "Write", "Task", "WebFetch", "WebSearch"];

// Tools to skip
const SKIP_TOOLS: &[&str] = &["Read", "Glob", "Grep", "LS"];

// Maximum content length to record
const MAX_CONTENT_LENGTH: usize = 500;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = input.tool_name.as_str();

    // Skip non-recordable tools
    if SKIP_TOOLS.contains(&tool_name) {
        return Ok(());
    }

    if !RECORDABLE_TOOLS.contains(&tool_name) {
        return Ok(());
    }

    let tool_output = input.tool_output.as_deref().unwrap_or("");

    // Record the result
    if record_tool_result(tool_name, &input.tool_input, tool_output) {
        // Silent recording - no output
    }

    Ok(())
}

fn record_tool_result(
    tool_name: &str,
    tool_input: &hook_common::input::ToolInput,
    tool_output: &str,
) -> bool {
    // Use global memory path (default: ~/.config/ai/memory/events.jsonl)
    let storage_path = match MemoryStorage::default_path() {
        Ok(path) => path,
        Err(e) => {
            eprintln!("Warning: Failed to determine memory storage path: {}", e);
            return false;
        }
    };
    let storage = MemoryStorage::new(storage_path);

    // Extract summary
    let summary = extract_tool_summary(tool_name, tool_input, tool_output);
    let success = determine_success(tool_output);

    // Build content
    let content = if success {
        format!("Tool: {}\n{}", tool_name, summary)
    } else {
        let error_preview = truncate_content(tool_output, 200);
        format!("[FAILURE] Tool: {}\n{}\nError: {}", tool_name, summary, error_preview)
    };

    let mut event = MemoryEvent::new(
        content,
        MemoryType::Observation,
        MemoryScope::Session,
        AgentType::Claude,
    );
    event.context = format!("tool:{}", tool_name);

    storage.append(&event).is_ok()
}

fn extract_tool_summary(
    tool_name: &str,
    tool_input: &hook_common::input::ToolInput,
    tool_output: &str,
) -> String {
    match tool_name {
        "Bash" => {
            let command = tool_input.command.as_deref().unwrap_or("");
            let first_line = command.lines().next().unwrap_or("");
            let truncated = if first_line.len() > 100 {
                &first_line[..100]
            } else {
                first_line
            };
            let success = !tool_output.to_lowercase().contains("error")
                && !tool_output.to_lowercase().contains("failed");
            format!(
                "Command: {} -> {}",
                truncated,
                if success { "Success" } else { "Failed" }
            )
        }
        "Edit" => {
            let file_path = tool_input.file_path.as_deref().unwrap_or("unknown");
            let filename = file_path.rsplit('/').next().unwrap_or(file_path);
            format!("Edited: {}", filename)
        }
        "Write" => {
            let file_path = tool_input.file_path.as_deref().unwrap_or("unknown");
            let filename = file_path.rsplit('/').next().unwrap_or(file_path);
            format!("Created: {}", filename)
        }
        "Task" => {
            let prompt = tool_input.prompt.as_deref().unwrap_or("");
            let truncated: String = prompt.chars().take(100).collect();
            let subagent = tool_input.subagent_type.as_deref().unwrap_or("unknown");
            format!("Task ({}): {}", subagent, truncated)
        }
        "WebFetch" => {
            let url = tool_input.extra.get("url").and_then(|v| v.as_str()).unwrap_or("unknown");
            format!("Fetched: {}", url)
        }
        "WebSearch" => {
            let query = tool_input.extra.get("query").and_then(|v| v.as_str()).unwrap_or("");
            format!("Searched: {}", query)
        }
        _ => format!("{} execution", tool_name),
    }
}

fn determine_success(tool_output: &str) -> bool {
    let output_lower = tool_output.to_lowercase();

    let failure_indicators = [
        "error:",
        "failed",
        "exception",
        "traceback",
        "permission denied",
        "not found",
        "command not found",
    ];

    for indicator in failure_indicators {
        if output_lower.contains(indicator) {
            return false;
        }
    }

    true
}

fn truncate_content(content: &str, max_length: usize) -> String {
    if content.len() <= max_length {
        content.to_string()
    } else {
        format!("{}...", &content[..max_length.saturating_sub(3)])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_determine_success() {
        assert!(determine_success("All tests passed"));
        assert!(!determine_success("Error: something failed"));
        assert!(!determine_success("Traceback (most recent call last):"));
    }

    #[test]
    fn test_truncate_content() {
        assert_eq!(truncate_content("short", 100), "short");
        let long = "a".repeat(200);
        let truncated = truncate_content(&long, 100);
        assert!(truncated.ends_with("..."));
        assert!(truncated.len() <= 100);
    }
}

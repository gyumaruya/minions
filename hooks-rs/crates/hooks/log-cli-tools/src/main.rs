//! PostToolUse hook: Log Codex/Gemini CLI input/output to JSONL file.
//!
//! Triggers after Bash tool calls containing 'codex' or 'gemini' commands.

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only process Bash tool calls
    if !input.is_bash() {
        return Ok(());
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()),
    };

    // Check if this is a codex or gemini command
    let is_codex = command.contains("codex");
    let is_gemini = command.contains("gemini");

    if !is_codex && !is_gemini {
        return Ok(());
    }

    // Extract prompt
    let prompt = if is_codex {
        extract_codex_prompt(command)
    } else {
        extract_gemini_prompt(command)
    };

    let prompt = match prompt {
        Some(p) => p,
        None => return Ok(()),
    };

    // Extract model
    let model = extract_model(command);

    // Get tool output (response)
    let output = input.tool_output.clone().unwrap_or_default();

    // Create log entry
    let entry = serde_json::json!({
        "timestamp": chrono_now(),
        "tool": if is_codex { "codex" } else { "gemini" },
        "model": model,
        "prompt": truncate_text(&prompt, 2000),
        "output": truncate_text(&output, 5000),
    });

    // Log to file
    log_entry(&entry)?;

    // Return context
    let context = format!(
        "[CLI Log] {} call recorded (prompt: {} chars, output: {} chars)",
        if is_codex { "Codex" } else { "Gemini" },
        prompt.len(),
        output.len()
    );

    let hook_output = HookOutput::post_tool_use().with_context(context);
    hook_output.write_stdout()?;

    Ok(())
}

/// Extract prompt from codex exec command.
fn extract_codex_prompt(command: &str) -> Option<String> {
    let patterns = [
        r#"codex\s+exec\s+.*?--full-auto\s+"([^"]+)""#,
        r#"codex\s+exec\s+.*?--full-auto\s+'([^']+)'"#,
        r#"codex\s+exec\s+.*?"([^"]+)"\s*2>/dev/null"#,
        r#"codex\s+exec\s+.*?'([^']+)'\s*2>/dev/null"#,
    ];

    for pattern in patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(command) {
                return Some(caps[1].trim().to_string());
            }
        }
    }
    None
}

/// Extract prompt from gemini command.
fn extract_gemini_prompt(command: &str) -> Option<String> {
    let patterns = [r#"gemini\s+-p\s+"([^"]+)""#, r#"gemini\s+-p\s+'([^']+)'"#];

    for pattern in patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(command) {
                return Some(caps[1].trim().to_string());
            }
        }
    }
    None
}

/// Extract model name from command.
fn extract_model(command: &str) -> Option<String> {
    let re = Regex::new(r"--model\s+(\S+)").ok()?;
    re.captures(command).map(|caps| caps[1].to_string())
}

/// Truncate text if too long.
fn truncate_text(text: &str, max_length: usize) -> String {
    if text.len() <= max_length {
        text.to_string()
    } else {
        format!(
            "{}... [truncated, {} total chars]",
            &text[..max_length],
            text.len()
        )
    }
}

/// Get current time in ISO 8601 format.
fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    format!("{}000", duration.as_secs())
}

/// Append entry to JSONL log file.
fn log_entry(entry: &serde_json::Value) -> Result<()> {
    let log_dir = get_log_dir();
    fs::create_dir_all(&log_dir)?;

    let log_file = log_dir.join("cli-tools.jsonl");
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_file)?;

    writeln!(file, "{}", serde_json::to_string(entry)?)?;
    Ok(())
}

/// Get log directory.
fn get_log_dir() -> PathBuf {
    if let Ok(project_dir) = std::env::var("CLAUDE_PROJECT_DIR") {
        PathBuf::from(project_dir).join(".claude").join("logs")
    } else {
        PathBuf::from(".claude").join("logs")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_codex_prompt() {
        let cmd = r#"codex exec --model gpt-5.2-codex --full-auto "Hello world""#;
        assert_eq!(extract_codex_prompt(cmd), Some("Hello world".to_string()));
    }

    #[test]
    fn test_extract_gemini_prompt() {
        let cmd = r#"gemini -p "Research topic""#;
        assert_eq!(extract_gemini_prompt(cmd), Some("Research topic".to_string()));
    }

    #[test]
    fn test_extract_model() {
        let cmd = "codex exec --model gpt-5.2-codex --full-auto test";
        assert_eq!(extract_model(cmd), Some("gpt-5.2-codex".to_string()));
    }

    #[test]
    fn test_truncate() {
        assert_eq!(truncate_text("short", 100), "short");
        let long = "a".repeat(200);
        let truncated = truncate_text(&long, 100);
        assert!(truncated.contains("truncated"));
    }
}

//! Debug logging for hooks.
//!
//! Logs all hook decisions to a JSONL file for debugging permission issues.

use chrono::{DateTime, Utc};
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

/// Debug log entry for hook execution
#[derive(Debug, Serialize)]
pub struct HookDebugLog {
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Hook name (e.g., "enforce-hierarchy")
    pub hook_name: String,
    /// Tool being checked
    pub tool_name: String,
    /// Tool input summary (truncated for large inputs)
    pub tool_input_summary: String,
    /// Agent role detected
    pub agent_role: String,
    /// Decision made (allow/deny/warn/skip)
    pub decision: String,
    /// Reason for the decision
    pub reason: String,
    /// Additional context
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context: Option<String>,
}

impl HookDebugLog {
    pub fn new(hook_name: &str, tool_name: &str) -> Self {
        Self {
            timestamp: Utc::now(),
            hook_name: hook_name.to_string(),
            tool_name: tool_name.to_string(),
            tool_input_summary: String::new(),
            agent_role: String::new(),
            decision: String::new(),
            reason: String::new(),
            context: None,
        }
    }

    pub fn with_tool_input(mut self, summary: &str) -> Self {
        // Truncate to 200 chars to avoid huge logs
        self.tool_input_summary = if summary.len() > 200 {
            format!("{}...", &summary[..200])
        } else {
            summary.to_string()
        };
        self
    }

    pub fn with_role(mut self, role: &str) -> Self {
        self.agent_role = role.to_string();
        self
    }

    pub fn with_decision(mut self, decision: &str, reason: &str) -> Self {
        self.decision = decision.to_string();
        self.reason = reason.to_string();
        self
    }

    pub fn with_context(mut self, context: &str) -> Self {
        self.context = Some(context.to_string());
        self
    }

    /// Write log entry to file
    pub fn write(&self) -> std::io::Result<()> {
        // Check if debug mode is enabled
        if !is_debug_enabled() {
            return Ok(());
        }

        let log_path = debug_log_path();

        // Ensure parent directory exists
        if let Some(parent) = log_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)?;

        let json = serde_json::to_string(self).unwrap_or_default();
        writeln!(file, "{}", json)?;

        Ok(())
    }
}

/// Check if debug mode is enabled
pub fn is_debug_enabled() -> bool {
    // Enable via environment variable
    if std::env::var("CLAUDE_HOOK_DEBUG").is_ok() {
        return true;
    }

    // Or check for debug marker file
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let marker = PathBuf::from(&project_dir)
        .join(".claude")
        .join(".hook-debug");
    marker.exists()
}

/// Get debug log file path
pub fn debug_log_path() -> PathBuf {
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(&project_dir)
        .join(".claude")
        .join("logs")
        .join("hook-debug.jsonl")
}

/// Quick helper to log a hook decision
pub fn log_decision(
    hook_name: &str,
    tool_name: &str,
    tool_input: &str,
    role: &str,
    decision: &str,
    reason: &str,
) {
    let log = HookDebugLog::new(hook_name, tool_name)
        .with_tool_input(tool_input)
        .with_role(role)
        .with_decision(decision, reason);

    let _ = log.write();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_debug_log_serialization() {
        let log = HookDebugLog::new("enforce-hierarchy", "Edit")
            .with_tool_input("file_path: src/main.rs")
            .with_role("conductor")
            .with_decision("deny", "Conductor cannot edit implementation files");

        let json = serde_json::to_string(&log).unwrap();
        assert!(json.contains("enforce-hierarchy"));
        assert!(json.contains("deny"));
    }

    #[test]
    fn test_truncation() {
        let long_input = "a".repeat(500);
        let log = HookDebugLog::new("test", "Bash").with_tool_input(&long_input);

        assert!(log.tool_input_summary.len() <= 203); // 200 + "..."
    }
}

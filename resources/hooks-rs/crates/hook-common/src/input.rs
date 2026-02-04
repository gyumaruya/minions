//! Hook input parsing from stdin.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{self, Read};

/// Main hook input structure received from Claude Code.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HookInput {
    /// The name of the tool being called (e.g., "Bash", "Edit", "Write")
    #[serde(default)]
    pub tool_name: String,

    /// Tool-specific input parameters
    #[serde(default)]
    pub tool_input: ToolInput,

    /// Tool output (for PostToolUse hooks)
    #[serde(default)]
    pub tool_output: Option<String>,

    /// Hook event name (for UserPromptSubmit hooks)
    #[serde(default)]
    pub hook_event_name: Option<String>,

    /// User prompt (for UserPromptSubmit hooks)
    #[serde(default)]
    pub user_prompt: Option<String>,

    /// Session ID
    #[serde(default)]
    pub session_id: Option<String>,

    /// Additional fields
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// Tool input parameters.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ToolInput {
    /// Command for Bash tool
    #[serde(default)]
    pub command: Option<String>,

    /// File path for Read/Edit/Write tools
    #[serde(default)]
    pub file_path: Option<String>,

    /// Content for Write tool
    #[serde(default)]
    pub content: Option<String>,

    /// Prompt for Task tool
    #[serde(default)]
    pub prompt: Option<String>,

    /// Subagent type for Task tool
    #[serde(default)]
    pub subagent_type: Option<String>,

    /// Additional fields
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

impl HookInput {
    /// Read and parse hook input from stdin.
    pub fn from_stdin() -> anyhow::Result<Self> {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;
        let parsed: HookInput = serde_json::from_str(&input)?;
        Ok(parsed)
    }

    /// Check if this is a Bash tool call.
    pub fn is_bash(&self) -> bool {
        self.tool_name == "Bash"
    }

    /// Check if this is an Edit tool call.
    pub fn is_edit(&self) -> bool {
        self.tool_name == "Edit"
    }

    /// Check if this is a Write tool call.
    pub fn is_write(&self) -> bool {
        self.tool_name == "Write"
    }

    /// Check if this is a Read tool call.
    pub fn is_read(&self) -> bool {
        self.tool_name == "Read"
    }

    /// Check if this is a Task tool call.
    pub fn is_task(&self) -> bool {
        self.tool_name == "Task"
    }

    /// Get the command if this is a Bash tool call.
    pub fn get_command(&self) -> Option<&str> {
        self.tool_input.command.as_deref()
    }

    /// Get the file path if applicable.
    pub fn get_file_path(&self) -> Option<&str> {
        self.tool_input.file_path.as_deref()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_bash_input() {
        let json = r#"{"tool_name": "Bash", "tool_input": {"command": "git status"}}"#;
        let input: HookInput = serde_json::from_str(json).unwrap();
        assert!(input.is_bash());
        assert_eq!(input.get_command(), Some("git status"));
    }

    #[test]
    fn test_parse_edit_input() {
        let json = r#"{"tool_name": "Edit", "tool_input": {"file_path": "/some/file.py"}}"#;
        let input: HookInput = serde_json::from_str(json).unwrap();
        assert!(input.is_edit());
        assert_eq!(input.get_file_path(), Some("/some/file.py"));
    }

    #[test]
    fn test_parse_user_prompt() {
        let json = r#"{"hook_event_name": "UserPromptSubmit", "user_prompt": "Hello"}"#;
        let input: HookInput = serde_json::from_str(json).unwrap();
        assert_eq!(input.hook_event_name, Some("UserPromptSubmit".to_string()));
        assert_eq!(input.user_prompt, Some("Hello".to_string()));
    }
}

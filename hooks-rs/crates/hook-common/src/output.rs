//! Hook output generation for stdout.

use serde::{Deserialize, Serialize};
use std::io::{self, Write};

/// Permission decision for PreToolUse hooks.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PermissionDecision {
    /// Allow the tool to proceed
    Allow,
    /// Ask user for confirmation
    Ask,
    /// Deny the tool
    Deny,
}

/// Hook-specific output structure.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HookSpecificOutput {
    /// Hook event name
    pub hook_event_name: String,

    /// Permission decision (for PreToolUse)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub permission_decision: Option<PermissionDecision>,

    /// Additional context message
    #[serde(skip_serializing_if = "Option::is_none")]
    pub additional_context: Option<String>,

    /// Blocking error message (causes hook to fail)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub blocking_error: Option<String>,
}

/// Main hook output structure.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HookOutput {
    /// Hook-specific output
    pub hook_specific_output: HookSpecificOutput,
}

impl HookOutput {
    /// Create a new hook output for PreToolUse.
    pub fn pre_tool_use(decision: PermissionDecision) -> Self {
        Self {
            hook_specific_output: HookSpecificOutput {
                hook_event_name: "PreToolUse".to_string(),
                permission_decision: Some(decision),
                additional_context: None,
                blocking_error: None,
            },
        }
    }

    /// Create a new hook output for PostToolUse.
    pub fn post_tool_use() -> Self {
        Self {
            hook_specific_output: HookSpecificOutput {
                hook_event_name: "PostToolUse".to_string(),
                permission_decision: None,
                additional_context: None,
                blocking_error: None,
            },
        }
    }

    /// Create a new hook output for UserPromptSubmit.
    pub fn user_prompt_submit() -> Self {
        Self {
            hook_specific_output: HookSpecificOutput {
                hook_event_name: "UserPromptSubmit".to_string(),
                permission_decision: None,
                additional_context: None,
                blocking_error: None,
            },
        }
    }

    /// Add additional context message.
    pub fn with_context(mut self, context: impl Into<String>) -> Self {
        self.hook_specific_output.additional_context = Some(context.into());
        self
    }

    /// Add blocking error (causes the hook to deny the operation).
    pub fn with_blocking_error(mut self, error: impl Into<String>) -> Self {
        self.hook_specific_output.blocking_error = Some(error.into());
        self
    }

    /// Allow the operation (PreToolUse only).
    pub fn allow() -> Self {
        Self::pre_tool_use(PermissionDecision::Allow)
    }

    /// Deny the operation (PreToolUse only).
    pub fn deny() -> Self {
        Self::pre_tool_use(PermissionDecision::Deny)
    }

    /// Ask user for confirmation (PreToolUse only).
    pub fn ask() -> Self {
        Self::pre_tool_use(PermissionDecision::Ask)
    }

    /// Write the output to stdout.
    pub fn write_stdout(&self) -> anyhow::Result<()> {
        let json = serde_json::to_string(self)?;
        io::stdout().write_all(json.as_bytes())?;
        io::stdout().flush()?;
        Ok(())
    }

    /// Write nothing to stdout (silent pass).
    pub fn silent() {
        // Do nothing - hook passes silently
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allow_output() {
        let output = HookOutput::allow();
        let json = serde_json::to_string(&output).unwrap();
        assert!(json.contains("\"permissionDecision\":\"allow\""));
    }

    #[test]
    fn test_deny_with_context() {
        let output = HookOutput::deny().with_context("Blocked for security");
        let json = serde_json::to_string(&output).unwrap();
        assert!(json.contains("\"permissionDecision\":\"deny\""));
        assert!(json.contains("Blocked for security"));
    }

    #[test]
    fn test_blocking_error() {
        let output = HookOutput::deny().with_blocking_error("Fatal error");
        let json = serde_json::to_string(&output).unwrap();
        assert!(json.contains("\"blockingError\":\"Fatal error\""));
    }
}

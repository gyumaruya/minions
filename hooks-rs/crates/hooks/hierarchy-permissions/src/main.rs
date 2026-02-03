//! PostToolUse hook: Hierarchy permission notification.
//!
//! When a Task tool spawns a subagent, provides context about
//! the permission inheritance from the agent hierarchy.

use anyhow::Result;
use hook_common::prelude::*;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = &input.tool_name;

    // Only process Task tool
    if tool_name != "Task" {
        return Ok(());
    }

    let prompt = input.tool_input.prompt.as_deref().unwrap_or("");

    // Determine roles
    let parent_role = get_agent_role();
    let target_role = detect_target_role(prompt);

    // Get permissions count
    let permissions_count = get_permissions_count(&parent_role, &target_role);

    if permissions_count > 0 {
        let message = format!(
            "Hierarchy: {} → {}. Permissions auto-granted: {} scopes.",
            parent_role, target_role, permissions_count
        );

        let output = HookOutput::post_tool_use().with_context(message);
        output.write_stdout()?;
    }

    Ok(())
}

fn get_agent_role() -> String {
    std::env::var("AGENT_ROLE")
        .unwrap_or_else(|_| "conductor".to_string())
        .to_lowercase()
}

fn detect_target_role(prompt: &str) -> String {
    let prompt_lower = prompt.to_lowercase();

    if prompt_lower.contains("section_leader") || prompt_lower.contains("セクションリーダー") {
        return "section_leader".to_string();
    }

    if prompt_lower.contains("musician") || prompt_lower.contains("演奏者") {
        return "musician".to_string();
    }

    "musician".to_string()
}

fn get_permissions_count(parent_role: &str, target_role: &str) -> usize {
    match (parent_role, target_role) {
        ("conductor", "section_leader") => 9, // Full permissions
        ("conductor", "musician") => 8,       // Limited bash
        ("section_leader", "musician") => 10, // Extended bash
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_target_role() {
        assert_eq!(detect_target_role("Assign to musician"), "musician");
        assert_eq!(
            detect_target_role("Delegate to section_leader"),
            "section_leader"
        );
        assert_eq!(detect_target_role("Some random task"), "musician");
    }

    #[test]
    fn test_get_permissions_count() {
        assert_eq!(get_permissions_count("conductor", "musician"), 8);
        assert_eq!(get_permissions_count("conductor", "section_leader"), 9);
        assert_eq!(get_permissions_count("section_leader", "musician"), 10);
        assert_eq!(get_permissions_count("musician", "anyone"), 0);
    }
}

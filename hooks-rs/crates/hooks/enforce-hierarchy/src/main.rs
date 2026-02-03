//! PreToolUse hook: Enforce agent hierarchy.
//!
//! Prevents upper-level agents (Conductor) from doing direct implementation work.
//! They must delegate to lower-level agents (Musicians).

use anyhow::Result;
use hook_common::prelude::*;
use std::path::Path;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = input.tool_name.as_str();

    // Only check Edit and Write tools
    if tool_name != "Edit" && tool_name != "Write" {
        return Ok(());
    }

    // Get file path
    let file_path = input.get_file_path().unwrap_or("");

    // Check if this file is allowed for upper agents
    if is_allowed_file(file_path) {
        return Ok(());
    }

    // Determine agent role
    let role = get_agent_role();

    // Musicians can edit anything
    if role == "musician" {
        return Ok(());
    }

    // Conductor should NOT directly edit implementation files
    if role == "conductor" {
        let message = "⛔ 階層違反: Conductor（指揮者）は直接ファイルを編集できません。\n\n\
            【正しい方法】\n\
            Task ツールでサブエージェント（Musician）を spawn して委譲してください。\n\n\
            → 詳細: .claude/rules/agent-hierarchy.md";

        let output = HookOutput::deny().with_context(message);
        output.write_stdout()?;
    }

    Ok(())
}

fn get_agent_role() -> String {
    let role = std::env::var("AGENT_ROLE").unwrap_or_default().to_lowercase();
    if role == "conductor" || role == "musician" {
        return role;
    }
    // Default: subagents are Musicians (safe default)
    "musician".to_string()
}

fn is_allowed_file(file_path: &str) -> bool {
    let path = Path::new(file_path);

    // Allow .claude/ config and documentation
    for component in path.components() {
        if component.as_os_str() == ".claude" {
            return true;
        }
        if component.as_os_str() == "memory" {
            return true;
        }
    }

    // Allow pyproject.toml, settings files
    if let Some(name) = path.file_name() {
        let name_str = name.to_string_lossy();
        if name_str == "pyproject.toml" || name_str == "settings.json" || name_str == ".gitignore"
        {
            return true;
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_allowed_file() {
        assert!(is_allowed_file(".claude/rules/test.md"));
        assert!(is_allowed_file("/project/.claude/settings.json"));
        assert!(is_allowed_file("memory/events.jsonl"));
        assert!(is_allowed_file("pyproject.toml"));
        assert!(!is_allowed_file("src/main.rs"));
        assert!(!is_allowed_file("lib/utils.py"));
    }
}

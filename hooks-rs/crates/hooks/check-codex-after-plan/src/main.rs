//! PostToolUse hook: Suggest Codex review after Plan tasks.
//!
//! Runs after Task tool execution and suggests Codex consultation
//! for reviewing plans and implementation strategies.

use anyhow::Result;
use hook_common::prelude::*;

// Task descriptions that suggest planning/design work
const PLAN_INDICATORS: &[&str] = &[
    "plan",
    "design",
    "architect",
    "structure",
    "implement",
    "strategy",
    "approach",
    "solution",
    "refactor",
    "migrate",
    "optimize",
];

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = &input.tool_name;

    // Only process Task tool
    if tool_name != "Task" {
        return Ok(());
    }

    if let Some(reason) = should_suggest_codex_review(&input.tool_input) {
        let context = format!(
            "[Codex Review Suggestion] {}. \
             Consider having Codex review this plan for potential improvements. \
             **Recommended**: Use Task tool with subagent_type='general-purpose' \
             to consult Codex and preserve main context.",
            reason
        );

        let output = HookOutput::post_tool_use().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn should_suggest_codex_review(tool_input: &hook_common::input::ToolInput) -> Option<String> {
    let subagent_type = tool_input
        .subagent_type
        .as_deref()
        .unwrap_or("")
        .to_lowercase();

    let description = tool_input
        .extra
        .get("description")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_lowercase();

    let prompt = tool_input
        .prompt
        .as_deref()
        .unwrap_or("")
        .to_lowercase();

    // Check if this is a Plan agent
    if subagent_type == "plan" {
        return Some("Plan task completed".to_string());
    }

    // Check description/prompt for planning keywords
    let combined_text = format!("{} {}", description, prompt);
    for indicator in PLAN_INDICATORS {
        if combined_text.contains(indicator) {
            return Some(format!("Task involves '{}'", indicator));
        }
    }

    None
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_plan_indicators() {
        let indicators = super::PLAN_INDICATORS;
        assert!(indicators.contains(&"plan"));
        assert!(indicators.contains(&"design"));
    }
}

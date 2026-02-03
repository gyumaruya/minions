//! UserPromptSubmit hook: Auto-learn from user interactions.
//!
//! Detects learning opportunities from user prompts:
//! - Corrections: 「〜にして」「違う」「〜じゃない」
//! - Preferences: 「〜がいい」「〜を使って」
//! - Workflows: 「いつも〜」「毎回〜」

use anyhow::Result;
use hook_common::prelude::*;
use camino::Utf8PathBuf;
use hook_memory::{AgentType, MemoryEvent, MemoryScope, MemoryStorage, MemoryType};
use regex::Regex;

// Maximum length for directives (longer text is likely conversational)
const MAX_DIRECTIVE_LENGTH: usize = 50;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let user_message = input.user_prompt.as_deref().unwrap_or("");

    if user_message.is_empty() {
        return Ok(());
    }

    // Detect learnings
    let learnings = detect_learning(user_message);

    // Save detected learnings
    let mut saved = 0;
    for (content, trigger, memory_type) in learnings {
        if save_learning(&content, &memory_type, &trigger) {
            saved += 1;
        }
    }

    // Add system message about learned content
    if saved > 0 {
        let context = format!("💡 {} 件の学習を記録しました。", saved);
        let output = HookOutput::user_prompt_submit().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn detect_learning(text: &str) -> Vec<(String, String, String)> {
    let mut learnings = Vec::new();

    // Skip questions
    if text.trim().ends_with('?')
        || text.trim().ends_with('？')
        || text.contains("の？")
        || text.contains("かな")
    {
        return learnings;
    }

    // Skip too long text
    if text.len() > MAX_DIRECTIVE_LENGTH {
        return learnings;
    }

    // Correction patterns
    let patterns: Vec<(&str, &str, &str)> = vec![
        (r"(.+)にして", "user_correction", "preference"),
        (r"(.+)に変えて", "user_correction", "preference"),
        (r"(.+)は違う", "user_correction", "preference"),
        (r"(.+)じゃない", "user_correction", "preference"),
        (r"(.+)ではなく(.+)", "user_correction", "preference"),
        (r"(.+)より(.+)がいい", "user_preference", "preference"),
        (r"(.+)を使って", "user_preference", "preference"),
        (r"(.+)を使わないで", "user_preference", "preference"),
        (r"いつも(.+)", "workflow", "workflow"),
        (r"毎回(.+)", "workflow", "workflow"),
        (r"常に(.+)", "workflow", "workflow"),
        (r"覚えて[：:]\s*(.+)", "explicit_learn", "preference"),
        (r"記憶して[：:]\s*(.+)", "explicit_learn", "preference"),
    ];

    for (pattern, trigger, memory_type) in patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(text) {
                let content = caps.get(0).map(|m| m.as_str()).unwrap_or("");
                learnings.push((
                    content.to_string(),
                    trigger.to_string(),
                    memory_type.to_string(),
                ));
            }
        }
    }

    learnings
}

fn save_learning(content: &str, memory_type: &str, trigger: &str) -> bool {
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let storage_path = Utf8PathBuf::from(&project_dir)
        .join(".claude")
        .join("memory")
        .join("events.jsonl");

    let storage = MemoryStorage::new(storage_path);

    let mtype = match memory_type {
        "workflow" => MemoryType::Workflow,
        _ => MemoryType::Preference,
    };

    let mut event = MemoryEvent::new(
        content.to_string(),
        mtype,
        MemoryScope::User,
        AgentType::Claude,
    );
    event.context = format!("auto-learn: {}", trigger);

    storage.append(&event).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_learning() {
        let learnings = detect_learning("PRは日本語にして");
        assert!(!learnings.is_empty());
        assert!(learnings[0].0.contains("日本語にして"));

        let learnings = detect_learning("毎回テストを先に書いて");
        assert!(!learnings.is_empty());
        assert_eq!(learnings[0].2, "workflow");
    }

    #[test]
    fn test_skip_questions() {
        let learnings = detect_learning("これでいい？");
        assert!(learnings.is_empty());
    }

    #[test]
    fn test_skip_long_text() {
        let long_text = "a".repeat(100);
        let learnings = detect_learning(&long_text);
        assert!(learnings.is_empty());
    }
}

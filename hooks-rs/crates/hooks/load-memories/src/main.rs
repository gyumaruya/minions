//! UserPromptSubmit hook: Load relevant memories at session start.
//!
//! Injects relevant memories (preferences, workflows, recent errors)
//! into the conversation context to guide behavior.

use anyhow::Result;
use hook_common::prelude::*;
use camino::Utf8PathBuf;
use hook_memory::{MemoryStorage, MemoryType};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

fn main() -> Result<()> {
    let _input = HookInput::from_stdin()?;

    // Check if we've already loaded memories this session
    let state_file = get_state_file();
    if state_file.exists() {
        return Ok(());
    }

    // Mark as loaded
    if let Some(parent) = state_file.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(&state_file, "loaded");

    // Get relevant memories
    let memories = get_relevant_memories();

    if memories.is_empty() {
        return Ok(());
    }

    // Format and inject as context
    let context = format_memories_for_context(&memories);

    let output = HookOutput::user_prompt_submit().with_context(context);
    output.write_stdout()?;

    Ok(())
}

fn get_state_file() -> PathBuf {
    let session_id = std::env::var("CLAUDE_SESSION_ID")
        .unwrap_or_else(|_| std::process::id().to_string());
    PathBuf::from("/tmp").join(format!("claude-memory-loaded-{}.flag", session_id))
}

fn get_relevant_memories() -> Vec<MemoryEntry> {
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let storage_path = Utf8PathBuf::from(&project_dir)
        .join(".claude")
        .join("memory")
        .join("events.jsonl");

    let storage = MemoryStorage::new(storage_path);

    let mut memories = Vec::new();

    // Get user preferences
    if let Ok(prefs) = storage.load_by_type(MemoryType::Preference) {
        for event in prefs.into_iter().take(5) {
            memories.push(MemoryEntry {
                content: event.content,
                memory_type: "preference".to_string(),
            });
        }
    }

    // Get workflows
    if let Ok(workflows) = storage.load_by_type(MemoryType::Workflow) {
        for event in workflows.into_iter().take(3) {
            memories.push(MemoryEntry {
                content: event.content,
                memory_type: "workflow".to_string(),
            });
        }
    }

    // Get recent errors
    if let Ok(errors) = storage.load_by_type(MemoryType::Error) {
        for event in errors.into_iter().take(3) {
            memories.push(MemoryEntry {
                content: event.content,
                memory_type: "error".to_string(),
            });
        }
    }

    // Dedupe by content
    let mut seen = std::collections::HashSet::new();
    memories.retain(|m| seen.insert(m.content.clone()));

    memories
}

struct MemoryEntry {
    content: String,
    memory_type: String,
}

fn format_memories_for_context(memories: &[MemoryEntry]) -> String {
    if memories.is_empty() {
        return String::new();
    }

    let mut lines = vec!["# 記憶から読み込んだ情報\n".to_string()];

    // Group by type
    let mut by_type: HashMap<&str, Vec<&str>> = HashMap::new();
    for m in memories {
        by_type
            .entry(&m.memory_type)
            .or_default()
            .push(&m.content);
    }

    let type_labels = [
        ("preference", "ユーザーの好み"),
        ("workflow", "ワークフロー"),
        ("error", "過去のエラーパターン"),
        ("decision", "設計判断"),
    ];

    for (mtype, label) in type_labels {
        if let Some(contents) = by_type.get(mtype) {
            lines.push(format!("\n## {}\n", label));
            for content in contents {
                lines.push(format!("- {}", content));
            }
        }
    }

    lines.push("\n---\n".to_string());
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_memories() {
        let memories = vec![
            MemoryEntry {
                content: "PRは日本語で書く".to_string(),
                memory_type: "preference".to_string(),
            },
            MemoryEntry {
                content: "テスト先に書く".to_string(),
                memory_type: "workflow".to_string(),
            },
        ];

        let context = format_memories_for_context(&memories);
        assert!(context.contains("ユーザーの好み"));
        assert!(context.contains("PRは日本語で書く"));
    }
}

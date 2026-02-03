//! PreToolUse hook: Recall relevant memories before tool execution.
//!
//! Searches for related memories before executing tools and injects
//! them as additional context for better decision-making.

use anyhow::Result;
use hook_common::prelude::*;
use hook_memory::MemoryStorage;

// Tools that benefit from memory recall
const RECALL_TOOLS: &[&str] = &["Bash", "Edit", "Write", "Task", "WebFetch", "WebSearch"];

// Maximum memories to inject
const MAX_RECALL: usize = 5;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = input.tool_name.as_str();

    // Skip tools that don't benefit from recall
    if !RECALL_TOOLS.contains(&tool_name) {
        return Ok(());
    }

    // Build search query
    let query = build_search_query(tool_name, &input.tool_input);

    // Recall relevant memories
    let memories = recall_memories(&query);

    if memories.is_empty() {
        return Ok(());
    }

    // Format and inject as context
    let context = format_memories_for_context(&memories);

    let output = HookOutput::allow().with_context(context);
    output.write_stdout()?;

    Ok(())
}

fn build_search_query(tool_name: &str, tool_input: &hook_common::input::ToolInput) -> String {
    match tool_name {
        "Bash" => {
            let command = tool_input.command.as_deref().unwrap_or("");
            let first_line = command.lines().next().unwrap_or("");
            let cmd_name = first_line.split_whitespace().next().unwrap_or("");
            format!("command {}", cmd_name)
        }
        "Edit" => {
            let file_path = tool_input.file_path.as_deref().unwrap_or("");
            let filename = file_path.rsplit('/').next().unwrap_or("");
            format!("edit {}", filename)
        }
        "Write" => {
            let file_path = tool_input.file_path.as_deref().unwrap_or("");
            let filename = file_path.rsplit('/').next().unwrap_or("");
            format!("create {}", filename)
        }
        "Task" => {
            let prompt = tool_input.prompt.as_deref().unwrap_or("");
            prompt.chars().take(200).collect()
        }
        "WebFetch" => {
            let url = tool_input.extra.get("url").and_then(|v| v.as_str()).unwrap_or("");
            format!("fetch {}", url)
        }
        "WebSearch" => tool_input.extra
            .get("query")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        _ => tool_name.to_string(),
    }
}

struct RecalledMemory {
    content: String,
    memory_type: String,
    score: f32,
}

fn recall_memories(query: &str) -> Vec<RecalledMemory> {
    // Use global memory path (default: ~/.config/ai/memory/events.jsonl)
    let storage = MemoryStorage::new(MemoryStorage::default_path());

    // Search memories
    let events = match storage.search(query) {
        Ok(e) => e,
        Err(_) => return Vec::new(),
    };

    events
        .into_iter()
        .take(MAX_RECALL)
        .map(|event| RecalledMemory {
            content: event.content,
            memory_type: format!("{:?}", event.memory_type),
            score: 0.8, // Simple fixed score for now
        })
        .collect()
}

fn format_memories_for_context(memories: &[RecalledMemory]) -> String {
    if memories.is_empty() {
        return String::new();
    }

    let mut lines = vec!["# 関連する記憶\n".to_string()];

    for (i, m) in memories.iter().enumerate() {
        let content = if m.content.len() > 150 {
            format!("{}...", &m.content[..147])
        } else {
            m.content.clone()
        };

        lines.push(format!(
            "{}. [{}] {} (関連度: {:.2})",
            i + 1,
            m.memory_type,
            content,
            m.score
        ));
    }

    lines.push("\n---\n".to_string());
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_recall_tools() {
        let tools = super::RECALL_TOOLS;
        assert!(tools.contains(&"Bash"));
        assert!(tools.contains(&"Edit"));
    }
}

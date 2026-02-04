//! PreToolUse hook: Enforce delegation for Conductor.
//!
//! 2-tier hierarchy: Conductor delegates to Musician.
//! Counts work tool usage without delegation and warns/blocks after thresholds.

use anyhow::Result;
use hook_common::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

const HOOK_NAME: &str = "enforce-delegation";
const WORK_TOOLS: &[&str] = &["Edit", "Write", "Read", "Bash", "WebFetch", "WebSearch"];
const DELEGATION_TOOL: &str = "Task";

// Thresholds for conductor
const WARN_THRESHOLD: i32 = 3;
const BLOCK_THRESHOLD: i32 = 5;

// 10-minute sliding window
const WINDOW_SECONDS: u64 = 600;

#[derive(Serialize, Deserialize, Default)]
struct DelegationState {
    last_delegation_ts: u64,
    non_delegate_count: i32,
    last_warning_at: i32,
    window_start_ts: u64,
}

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = &input.tool_name;
    let tool_input = &input.tool_input;

    let role = get_role();

    // Musicians have no restrictions
    if role == "musician" {
        log_decision(
            HOOK_NAME,
            tool_name,
            "",
            &role,
            "skip",
            "Musician has no restrictions",
        );
        return Ok(());
    }

    let state_file = state_path(&role);
    let mut state = load_state(&state_file);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    // Reset window if expired (10 minutes)
    if state.window_start_ts > 0 && now - state.window_start_ts > WINDOW_SECONDS {
        log_decision(
            HOOK_NAME,
            tool_name,
            "",
            &role,
            "reset",
            "Window expired, resetting counter",
        );
        state.non_delegate_count = 0;
        state.window_start_ts = now;
    }

    // Handle delegation (Task tool with proper hierarchy)
    if tool_name == DELEGATION_TOOL {
        if is_delegation_from_tool_input(tool_input) {
            log_decision(
                HOOK_NAME,
                tool_name,
                "",
                &role,
                "delegation",
                "Delegation detected, resetting counter",
            );
            state.last_delegation_ts = now;
            state.non_delegate_count = 0;
            state.window_start_ts = now;
            save_state(&state_file, &state);
            return Ok(());
        }
    }

    // Handle work tools
    if WORK_TOOLS.contains(&tool_name.as_str()) {
        // Check allowlist for Edit/Write/Read
        if tool_name == "Edit" || tool_name == "Write" || tool_name == "Read" {
            if let Some(file_path) = input.get_file_path() {
                if is_allowed_path(file_path) {
                    log_decision(
                        HOOK_NAME,
                        tool_name,
                        file_path,
                        &role,
                        "allow",
                        "File in allowlist",
                    );
                    return Ok(());
                }
            }
        }

        // Initialize window if needed
        if state.window_start_ts == 0 {
            state.window_start_ts = now;
        }

        state.non_delegate_count += 1;

        // Block if over threshold
        if state.non_delegate_count >= BLOCK_THRESHOLD {
            let message = format!(
                "⛔ 階層違反: {} は直接作業を継続できません。\n\
                 連続 {} 回の作業ツール使用。\n\
                 Task ツールで下位エージェント（musician）へ委譲してください。",
                role, state.non_delegate_count
            );

            log_decision(
                HOOK_NAME,
                tool_name,
                "",
                &role,
                "deny",
                &format!("Block threshold reached: {}/{}", state.non_delegate_count, BLOCK_THRESHOLD),
            );

            let output = HookOutput::deny().with_context(&message);
            output.write_stdout()?;
            save_state(&state_file, &state);
            return Ok(());
        }

        // Always remind about delegation
        let mut reminder = format!(
            "💡 委譲推奨: Task ツールで musician へ委譲できます。（{}/{}）",
            state.non_delegate_count, BLOCK_THRESHOLD
        );

        // Add stronger warning if approaching threshold
        if state.non_delegate_count >= WARN_THRESHOLD {
            if state.last_warning_at < state.non_delegate_count {
                state.last_warning_at = state.non_delegate_count;
                reminder = format!(
                    "⚠ 委譲なし作業が {} 回です（{}回でブロック）。\n\
                     Task ツールで委譲を検討してください。",
                    state.non_delegate_count, BLOCK_THRESHOLD
                );
            }
        }

        log_decision(
            HOOK_NAME,
            tool_name,
            "",
            &role,
            "warn",
            &format!("Work tool count: {}/{}", state.non_delegate_count, BLOCK_THRESHOLD),
        );

        let output = HookOutput::allow().with_context(reminder);
        output.write_stdout()?;
    } else {
        log_decision(
            HOOK_NAME,
            tool_name,
            "",
            &role,
            "skip",
            "Not a work tool",
        );
    }

    save_state(&state_file, &state);
    Ok(())
}

fn get_role() -> String {
    // 1. PRIORITY: Check if we're a subagent first (TTY check)
    // This prevents inheriting AGENT_ROLE from parent
    if is_subagent() {
        return "musician".to_string();
    }

    // 2. Check environment variable (explicit override for main session)
    if let Ok(role) = std::env::var("AGENT_ROLE") {
        let role_lower = role.to_lowercase();
        if role_lower == "conductor" || role_lower == "musician" {
            return role_lower;
        }
    }

    // 3. Check conductor-session marker for main session
    if is_conductor_session() {
        return "conductor".to_string();
    }

    // 4. Safe default: musician
    "musician".to_string()
}

fn is_subagent() -> bool {
    // 1. If CLAUDE_SUBAGENT is set, we're definitely a subagent
    if std::env::var("CLAUDE_SUBAGENT").is_ok() {
        return true;
    }

    // 2. Subagents typically don't have a controlling TTY
    // Main sessions run in terminal with TTY attached
    #[cfg(unix)]
    {
        use std::os::unix::io::AsRawFd;

        // Check if stdin is a TTY
        let stdin_is_tty = unsafe { libc::isatty(std::io::stdin().as_raw_fd()) } == 1;

        // If no TTY, likely a subagent
        if !stdin_is_tty {
            return true;
        }
    }

    false
}

fn is_conductor_session() -> bool {
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let marker_path = PathBuf::from(project_dir)
        .join(".claude")
        .join(".conductor-session");
    marker_path.exists()
}

fn state_path(role: &str) -> PathBuf {
    // Use project directory for stable session identification
    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());

    // Create a hash of project dir to use as session key
    let project_hash: u64 = project_dir.bytes().fold(0u64, |acc, b| {
        acc.wrapping_mul(31).wrapping_add(b as u64)
    });

    PathBuf::from("/tmp").join(format!("claude-delegation-{:x}-{}.json", project_hash, role))
}

fn load_state(path: &PathBuf) -> DelegationState {
    fs::read_to_string(path)
        .ok()
        .and_then(|content| serde_json::from_str(&content).ok())
        .unwrap_or_default()
}

fn save_state(path: &PathBuf, state: &DelegationState) {
    if let Ok(content) = serde_json::to_string(state) {
        let tmp = path.with_extension("tmp");
        if fs::write(&tmp, &content).is_ok() {
            let _ = fs::rename(&tmp, path);
        }
    }
}

fn is_allowed_path(file_path: &str) -> bool {
    // .claude/ directory is always allowed
    if file_path.contains(".claude") {
        return true;
    }
    // memory/ directory is always allowed
    if file_path.contains("memory") {
        return true;
    }
    // Specific config files are allowed
    let filename = file_path.rsplit('/').next().unwrap_or("");
    matches!(filename, "pyproject.toml" | "settings.json" | ".gitignore")
}

fn is_delegation_from_tool_input(tool_input: &hook_common::input::ToolInput) -> bool {
    // Check for hierarchy keywords in prompt
    if let Some(prompt) = &tool_input.prompt {
        if prompt.to_lowercase().contains("musician") {
            return true;
        }
    }
    // Check for subagent_type
    if tool_input.subagent_type.is_some() {
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_allowed_path() {
        assert!(is_allowed_path(".claude/rules/test.md"));
        assert!(is_allowed_path("/project/memory/events.jsonl"));
        assert!(is_allowed_path("pyproject.toml"));
        assert!(is_allowed_path("/project/settings.json"));
        assert!(!is_allowed_path("src/main.rs"));
    }
}

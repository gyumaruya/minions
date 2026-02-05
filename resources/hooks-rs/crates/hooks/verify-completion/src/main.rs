//! PostAssistantResponse hook: Verify task completion.
//!
//! Detects completion markers/keywords in assistant responses and triggers
//! verification by another agent (Copilot or Codex).

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;
use std::process::Command;

const HOOK_NAME: &str = "verify-completion";

// Explicit markers (highest priority)
const EXPLICIT_MARKERS: &[&str] = &["[[VERIFY:done]]", "[[VERIFY:error]]"];

// Completion keywords (fallback - must be near end of response)
const COMPLETION_KEYWORDS_JA: &[&str] = &["作業完了", "実装完了", "完了しました"];
const COMPLETION_KEYWORDS_EN: &[&str] = &["work complete", "implementation complete", "done"];

// Cooldown to prevent duplicate verifications
const COOLDOWN_SECONDS: u64 = 300; // 5 minutes

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Get assistant response
    let response = input.assistant_response.as_deref().unwrap_or("");

    // Check for explicit markers first
    if has_explicit_marker(response) {
        trigger_verification("explicit_marker", response)?;
        return Ok(());
    }

    // Check for completion keywords near end
    if has_completion_keyword(response) {
        trigger_verification("completion_keyword", response)?;
        return Ok(());
    }

    Ok(())
}

fn has_explicit_marker(response: &str) -> bool {
    EXPLICIT_MARKERS.iter().any(|marker| response.contains(marker))
}

fn has_completion_keyword(response: &str) -> bool {
    // Only check last 500 characters to avoid false positives
    let tail = if response.len() > 500 {
        &response[response.len() - 500..]
    } else {
        response
    };

    let tail_lower = tail.to_lowercase();

    // Check Japanese keywords
    if COMPLETION_KEYWORDS_JA.iter().any(|kw| tail_lower.contains(kw)) {
        return true;
    }

    // Check English keywords (word boundary required)
    for kw in COMPLETION_KEYWORDS_EN {
        let pattern = format!(r"\b{}\b", regex::escape(kw));
        if Regex::new(&pattern).unwrap().is_match(&tail_lower) {
            return true;
        }
    }

    false
}

fn trigger_verification(trigger_type: &str, _response: &str) -> Result<()> {
    log_decision(
        HOOK_NAME,
        "PostAssistantResponse",
        "",
        trigger_type,
        "trigger",
        "Completion detected, triggering verification",
    );

    // Call verification agent (Copilot by default)
    let verification_result = run_verification_agent();

    match verification_result {
        Ok(report) => {
            // Append verification report to context
            let message = format!(
                "\n\n---\n\n**🔍 自動検証レポート**\n\n{}\n\n---",
                report
            );

            let output = HookOutput::post_assistant_response().with_context(message);
            output.write_stdout()?;
        }
        Err(e) => {
            log_decision(
                HOOK_NAME,
                "verification",
                "",
                "",
                "error",
                &format!("Verification failed: {}", e),
            );
        }
    }

    Ok(())
}

fn run_verification_agent() -> Result<String> {
    // Profile: quick (default)
    let prompt = r#"
サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

# Verification Task

以下を確認してください:

1. **変更確認**: git status, git diff で変更内容を確認
2. **未完了タスク**: 残りタスクがないか確認
3. **問題点**: エラーや警告がないか確認

## 出力形式

✅ **完了**: 問題なし
⚠️ **注意**: [問題の説明]
❌ **未完了**: [残りタスク]

簡潔に報告してください（5行以内）。
"#;

    let output = Command::new("copilot")
        .arg("-p")
        .arg(prompt)
        .arg("--model")
        .arg("sonnet")
        .arg("--allow-all")
        .arg("--silent")
        .output()?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Err(anyhow::anyhow!("Verification agent failed"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_has_explicit_marker() {
        assert!(has_explicit_marker("Some text [[VERIFY:done]]"));
        assert!(has_explicit_marker("Error occurred [[VERIFY:error]]"));
        assert!(!has_explicit_marker("Normal response without marker"));
    }

    #[test]
    fn test_has_completion_keyword() {
        // Should match near end
        assert!(has_completion_keyword("Some work... 作業完了しました。"));
        assert!(has_completion_keyword("Implementation done."));

        // Should not match in middle
        assert!(!has_completion_keyword("作業完了の予定です。まだ途中です。".repeat(100).as_str()));
    }
}

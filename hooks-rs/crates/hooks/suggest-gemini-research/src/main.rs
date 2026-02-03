//! PreToolUse hook: Suggest Gemini for research tasks.
//!
//! Analyzes web search/fetch operations and suggests using Gemini CLI
//! for comprehensive research with its larger context window.

use anyhow::Result;
use hook_common::prelude::*;

// Keywords that suggest deep research would benefit from Gemini
const RESEARCH_INDICATORS: &[&str] = &[
    "documentation",
    "best practice",
    "comparison",
    "library",
    "framework",
    "tutorial",
    "guide",
    "example",
    "pattern",
    "architecture",
    "migration",
    "upgrade",
    "breaking change",
    "api reference",
    "specification",
];

// Simple lookups that don't need Gemini
const SIMPLE_LOOKUP_PATTERNS: &[&str] = &[
    "error message",
    "stack trace",
    "version",
    "release notes",
    "changelog",
];

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let tool_name = input.tool_name.as_str();

    // Only process WebSearch and WebFetch
    if tool_name != "WebSearch" && tool_name != "WebFetch" {
        return Ok(());
    }

    // Get query/url based on tool type
    let (query, url) = if tool_name == "WebSearch" {
        (
            input.tool_input.extra
                .get("query")
                .and_then(|v| v.as_str())
                .unwrap_or(""),
            "",
        )
    } else {
        (
            input.tool_input.prompt.as_deref().unwrap_or(""),
            input.tool_input.extra
                .get("url")
                .and_then(|v| v.as_str())
                .unwrap_or(""),
        )
    };

    if let Some(reason) = should_suggest_gemini(query, url) {
        let context = format!(
            "[Gemini Research Suggestion] {}. \
             For comprehensive research, consider using Gemini CLI (1M token context). \
             **Recommended**: Use Task tool with subagent_type='general-purpose' \
             to consult Gemini and save results to .claude/docs/research/. \
             (Direct call OK for quick questions: `gemini -p '...' 2>/dev/null`)",
            reason
        );

        let output = HookOutput::allow().with_context(context);
        output.write_stdout()?;
    }

    Ok(())
}

fn should_suggest_gemini(query: &str, url: &str) -> Option<String> {
    let query_lower = query.to_lowercase();
    let url_lower = url.to_lowercase();
    let combined = format!("{} {}", query_lower, url_lower);

    // Skip simple lookups
    for pattern in SIMPLE_LOOKUP_PATTERNS {
        if combined.contains(pattern) {
            return None;
        }
    }

    // Check for research indicators
    for indicator in RESEARCH_INDICATORS {
        if combined.contains(indicator) {
            return Some(format!("Research involves '{}'", indicator));
        }
    }

    // Long queries suggest complex research
    if query.len() > 100 {
        return Some("Complex research query detected".to_string());
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_should_suggest_gemini() {
        assert!(should_suggest_gemini("best practice for rust", "").is_some());
        assert!(should_suggest_gemini("", "https://docs.rs/library").is_some());
        assert!(should_suggest_gemini("error message fix", "").is_none());
        assert!(should_suggest_gemini("short query", "").is_none());
    }
}

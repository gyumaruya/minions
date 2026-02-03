//! UserPromptSubmit hook: Route to appropriate agent based on user intent.
//!
//! Priority:
//! 1. Codex - Design, debugging, deep reasoning
//! 2. Gemini - Research, multimodal, large context
//! 3. Copilot - Everything else (cost-effective default)

use anyhow::Result;
use hook_common::prelude::*;

// Triggers for Codex (design, debugging, deep reasoning)
const CODEX_TRIGGERS_JA: &[&str] = &[
    "設計", "どう設計", "アーキテクチャ",
    "なぜ動かない", "エラー", "バグ", "デバッグ",
    "どちらがいい", "比較して", "トレードオフ",
    "実装方法", "どう実装",
    "リファクタリング", "リファクタ",
    "レビュー",
    "考えて", "分析して", "深く",
    "セキュリティ", "パフォーマンス",
];

const CODEX_TRIGGERS_EN: &[&str] = &[
    "design", "architecture", "architect",
    "debug", "error", "bug", "not working", "fails",
    "compare", "trade-off", "tradeoff", "which is better",
    "how to implement", "implementation",
    "refactor", "simplify",
    "review",
    "think", "analyze", "deeply",
    "security", "performance", "optimize",
];

// Triggers for Gemini (research, multimodal, large context)
const GEMINI_TRIGGERS_JA: &[&str] = &[
    "調べて", "リサーチ", "調査",
    "PDF", "動画", "音声", "画像",
    "コードベース全体", "リポジトリ全体",
    "最新", "ドキュメント",
    "ライブラリ", "パッケージ",
    "Web検索", "ググって",
];

const GEMINI_TRIGGERS_EN: &[&str] = &[
    "research", "investigate", "look up", "find out",
    "pdf", "video", "audio", "image",
    "entire codebase", "whole repository",
    "latest", "documentation", "docs",
    "library", "package", "framework",
    "web search", "google",
];

// Direct tasks (no delegation needed)
const DIRECT_TASKS: &[&str] = &[
    "jj commit", "jj push", "jj status", "jj log", "jj diff",
    "git commit", "git push", "git status", "git log", "git diff",
    "コミットして", "プッシュして",
    "ファイル作成", "ファイル編集",
    "create file", "edit file",
];

#[derive(Debug, PartialEq)]
enum Agent {
    Direct,
    Codex,
    Gemini,
    Copilot,
}

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    let prompt = input.user_prompt.as_deref().unwrap_or("");

    // Skip very short prompts
    if prompt.len() < 10 {
        return Ok(());
    }

    let (agent, trigger) = detect_agent(prompt);

    let context = match agent {
        Agent::Direct => return Ok(()),
        Agent::Codex => format!(
            "[Agent: Codex] Detected '{}' - important task requiring deep reasoning. \
             Use Codex for design decisions, debugging, or complex analysis. \
             Command: `codex exec --model gpt-5.2-codex --sandbox read-only --full-auto \"...\"` \
             (via subagent for large outputs)",
            trigger
        ),
        Agent::Gemini => format!(
            "[Agent: Gemini] Detected '{}' - specialized research/multimodal task. \
             Use Gemini for research, large context analysis, or multimodal content. \
             Command: `gemini -p \"...\" 2>/dev/null` \
             (via subagent for large outputs)",
            trigger
        ),
        Agent::Copilot => format!(
            "[Agent: Copilot] General task - consider using Copilot CLI for cost-effective \
             execution with subagent capabilities. \
             Command: `copilot -p \"...\" --model claude-opus-4.5 --allow-all --silent 2>/dev/null` \
             (direct call OK for quick tasks)"
        ),
    };

    let output = HookOutput::user_prompt_submit().with_context(context);
    output.write_stdout()?;

    Ok(())
}

fn detect_agent(prompt: &str) -> (Agent, String) {
    let prompt_lower = prompt.to_lowercase();

    // Check direct tasks first
    for task in DIRECT_TASKS {
        if prompt_lower.contains(&task.to_lowercase()) {
            return (Agent::Direct, task.to_string());
        }
    }

    // Priority 1: Codex triggers
    for trigger in CODEX_TRIGGERS_JA.iter().chain(CODEX_TRIGGERS_EN.iter()) {
        if prompt_lower.contains(&trigger.to_lowercase()) {
            return (Agent::Codex, trigger.to_string());
        }
    }

    // Priority 2: Gemini triggers
    for trigger in GEMINI_TRIGGERS_JA.iter().chain(GEMINI_TRIGGERS_EN.iter()) {
        if prompt_lower.contains(&trigger.to_lowercase()) {
            return (Agent::Gemini, trigger.to_string());
        }
    }

    // Priority 3: Copilot for non-trivial prompts
    if prompt.len() > 20 {
        return (Agent::Copilot, "general task".to_string());
    }

    (Agent::Direct, String::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_codex() {
        let (agent, _) = detect_agent("このエラーをデバッグして");
        assert_eq!(agent, Agent::Codex);

        let (agent, _) = detect_agent("How should I design this feature?");
        assert_eq!(agent, Agent::Codex);
    }

    #[test]
    fn test_detect_gemini() {
        let (agent, _) = detect_agent("このライブラリについて調べて");
        assert_eq!(agent, Agent::Gemini);

        let (agent, _) = detect_agent("Research the latest documentation");
        assert_eq!(agent, Agent::Gemini);
    }

    #[test]
    fn test_detect_direct() {
        let (agent, _) = detect_agent("git commit please");
        assert_eq!(agent, Agent::Direct);
    }
}

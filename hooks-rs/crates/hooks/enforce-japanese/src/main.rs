//! Enforce Japanese for user-facing content.
//!
//! Intercepts gh pr create and git commit to ensure
//! titles/messages are in Japanese.

use anyhow::Result;
use hook_common::prelude::*;
use regex::Regex;

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only check Bash commands
    if !input.is_bash() {
        return Ok(());
    }

    let command = match input.get_command() {
        Some(cmd) => cmd,
        None => return Ok(()),
    };

    // Check if this is a PR or commit command
    let pr_create = Regex::new(r"gh\s+pr\s+create").unwrap();
    let commit = Regex::new(r"git\s+commit").unwrap();

    let is_pr_create = pr_create.is_match(command);
    let is_commit = commit.is_match(command);

    if !is_pr_create && !is_commit {
        return Ok(());
    }

    // Extract title/message
    if let Some(title_or_message) = extract_title_or_message(command) {
        if !contains_japanese(&title_or_message) {
            let action_type = if is_pr_create {
                "PRタイトル"
            } else {
                "コミットメッセージ"
            };

            let message = format!(
                "⚠️ {}は日本語で記述してください。\n\n現在の内容: {}\n\n日本語に書き換えて再実行してください。",
                action_type, title_or_message
            );

            let output = HookOutput::deny().with_context(message);
            output.write_stdout()?;
        }
    }

    Ok(())
}

/// Check if text contains Japanese characters.
fn contains_japanese(text: &str) -> bool {
    for c in text.chars() {
        // Hiragana: U+3040-U+309F
        // Katakana: U+30A0-U+30FF
        // Kanji: U+4E00-U+9FFF
        // Full-width: U+FF00-U+FFEF
        if ('\u{3040}'..='\u{309F}').contains(&c)
            || ('\u{30A0}'..='\u{30FF}').contains(&c)
            || ('\u{4E00}'..='\u{9FFF}').contains(&c)
            || ('\u{FF00}'..='\u{FFEF}').contains(&c)
        {
            return true;
        }
    }
    false
}

/// Extract title/message from command.
fn extract_title_or_message(command: &str) -> Option<String> {
    // --title "..." or --title '...'
    let title_re = Regex::new(r#"--title\s+["']([^"']+)["']"#).unwrap();
    if let Some(caps) = title_re.captures(command) {
        return Some(caps[1].to_string());
    }

    // -m "..." or -m '...'
    let msg_re = Regex::new(r#"-m\s+["']([^"']+)["']"#).unwrap();
    if let Some(caps) = msg_re.captures(command) {
        return Some(caps[1].to_string());
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_contains_japanese() {
        assert!(contains_japanese("日本語"));
        assert!(contains_japanese("テスト"));
        assert!(contains_japanese("ひらがな"));
        assert!(!contains_japanese("English only"));
        assert!(!contains_japanese("123"));
    }

    #[test]
    fn test_extract_title() {
        assert_eq!(
            extract_title_or_message(r#"gh pr create --title "Test""#),
            Some("Test".to_string())
        );
        assert_eq!(
            extract_title_or_message(r#"gh pr create --title '機能追加'"#),
            Some("機能追加".to_string())
        );
    }

    #[test]
    fn test_extract_message() {
        assert_eq!(
            extract_title_or_message(r#"git commit -m "Add feature""#),
            Some("Add feature".to_string())
        );
        assert_eq!(
            extract_title_or_message(r#"git commit -m '修正'"#),
            Some("修正".to_string())
        );
    }
}

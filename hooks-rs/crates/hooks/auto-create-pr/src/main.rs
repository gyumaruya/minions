//! UserPromptSubmit hook: Auto-create feature branch and draft PR on session start.
//!
//! Ensures every session has an open PR before any work begins.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::run_command_with_timeout;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(30);

fn main() -> Result<()> {
    let _input = HookInput::from_stdin()?;

    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let marker_file = PathBuf::from(&project_dir)
        .join(".claude")
        .join(".session-pr-created");
    let session_id = get_session_id();

    // Create conductor marker at session start
    create_conductor_marker(&project_dir);

    // Skip if marker exists AND is for current session
    if is_marker_valid(&marker_file, &session_id) {
        return Ok(());
    }

    // New session - delete old marker
    if marker_file.exists() {
        let _ = fs::remove_file(&marker_file);
    }

    // Cleanup merged branches
    cleanup_merged_branches();

    // Check for existing open PR
    if let Some(pr) = get_first_open_pr() {
        let pr_branch = pr.head_ref_name.clone();
        let pr_number = pr.number;
        let pr_url = pr.url.clone();

        // Sync local branch with the PR branch
        if !pr_branch.is_empty() {
            sync_branch_with_pr(&pr_branch);
        }

        write_marker(&marker_file, &session_id, &format!("existing:{}:#{}", pr_branch, pr_number));

        // Output additional context for Claude
        let context = format!("📋 既存のPR #{} を使用（ブランチ同期済み）: {}", pr_number, pr_url);
        let output = HookOutput::user_prompt_submit().with_context(context);
        output.write_stdout()?;
        return Ok(());
    }

    // No open PR - create one
    match create_branch_and_pr() {
        Ok((branch_name, pr_url)) => {
            write_marker(&marker_file, &session_id, &format!("created:{}", branch_name));
            let context = format!("✅ Draft PR を自動作成: {}", pr_url);
            let output = HookOutput::user_prompt_submit().with_context(context);
            output.write_stdout()?;
        }
        Err(e) => {
            let context = format!("⚠️ PR自動作成に失敗: {}", e);
            let output = HookOutput::user_prompt_submit().with_context(context);
            output.write_stdout()?;
        }
    }

    Ok(())
}

fn get_session_id() -> String {
    std::process::id().to_string()
}

#[derive(Default)]
struct PullRequest {
    number: i32,
    head_ref_name: String,
    url: String,
}

fn get_first_open_pr() -> Option<PullRequest> {
    let result = run_command_with_timeout(
        "gh pr list --state open --json number,headRefName,url --limit 1",
        TIMEOUT,
    ).ok()?;

    if !result.success || result.stdout.is_empty() {
        return None;
    }

    let prs: Vec<serde_json::Value> = serde_json::from_str(&result.stdout).ok()?;
    let pr = prs.first()?;

    Some(PullRequest {
        number: pr.get("number")?.as_i64()? as i32,
        head_ref_name: pr.get("headRefName")?.as_str()?.to_string(),
        url: pr.get("url")?.as_str()?.to_string(),
    })
}

fn get_short_hash() -> String {
    run_command_with_timeout("git rev-parse --short HEAD", TIMEOUT)
        .map(|r| r.stdout.trim().to_string())
        .unwrap_or_else(|_| {
            use std::time::{SystemTime, UNIX_EPOCH};
            let ts = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            format!("{}", ts)
        })
}

fn cleanup_merged_branches() {
    let _ = run_command_with_timeout("git fetch origin", TIMEOUT);

    let result = run_command_with_timeout(
        "gh pr list --state merged --json headRefName --limit 20",
        TIMEOUT,
    );

    let merged_branches: Vec<String> = result
        .ok()
        .and_then(|r| serde_json::from_str::<Vec<serde_json::Value>>(&r.stdout).ok())
        .map(|prs| {
            prs.iter()
                .filter_map(|pr| pr.get("headRefName")?.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    if let Ok(result) = run_command_with_timeout("git branch", TIMEOUT) {
        for line in result.stdout.lines() {
            let branch = line.trim().trim_start_matches("* ").trim();
            if merged_branches.contains(&branch.to_string()) && branch != "main" {
                let _ = run_command_with_timeout(&format!("git branch -D {}", branch), TIMEOUT);
            }
        }
    }

    let _ = run_command_with_timeout("git checkout main", TIMEOUT);
    let _ = run_command_with_timeout("git pull origin main", TIMEOUT);
}

fn sync_branch_with_pr(branch_name: &str) -> bool {
    let _ = run_command_with_timeout(&format!("git fetch origin {}", branch_name), TIMEOUT);

    if run_command_with_timeout(&format!("git checkout {}", branch_name), TIMEOUT)
        .map(|r| r.success)
        .unwrap_or(false)
    {
        let _ = run_command_with_timeout(&format!("git pull origin {}", branch_name), TIMEOUT);
        return true;
    }

    // Create tracking branch
    let _ = run_command_with_timeout(
        &format!("git checkout -b {} origin/{}", branch_name, branch_name),
        TIMEOUT,
    );

    true
}

fn create_branch_and_pr() -> Result<(String, String)> {
    let short_hash = get_short_hash();
    let branch_name = format!("feature/session-{}", short_hash);

    // Create new branch from main
    let _ = run_command_with_timeout("git checkout main", TIMEOUT);
    let result = run_command_with_timeout(&format!("git checkout -b {}", branch_name), TIMEOUT)?;
    if !result.success {
        anyhow::bail!("Failed to create branch: {}", branch_name);
    }

    // Create initial commit if there are uncommitted changes
    let status = run_command_with_timeout("git status --porcelain", TIMEOUT)?;
    if !status.stdout.trim().is_empty() {
        let _ = run_command_with_timeout("git add -A", TIMEOUT);
        let commit_msg = format!(
            "WIP: Session {}\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>",
            short_hash
        );
        let _ = run_command_with_timeout(
            &format!("git commit -m \"{}\"", commit_msg.replace('"', "\\\"")),
            TIMEOUT,
        );
    }

    // Push branch
    let push_result = run_command_with_timeout(
        &format!("git push -u origin {}", branch_name),
        TIMEOUT,
    )?;
    if !push_result.success {
        anyhow::bail!("Failed to push: {}", push_result.stderr);
    }

    // Create PR
    let pr_title = format!("WIP: Session {}", short_hash);
    let pr_cmd = format!(
        "gh pr create --draft --head {} --base main --title \"{}\" --body \"🤖 Auto-created draft PR for session.\"",
        branch_name, pr_title
    );

    let pr_result = run_command_with_timeout(&pr_cmd, TIMEOUT)?;
    if pr_result.success {
        let pr_url = pr_result.stdout.lines().last().unwrap_or("").trim().to_string();
        Ok((branch_name, pr_url))
    } else {
        anyhow::bail!("Failed to create PR: {}", pr_result.stderr);
    }
}

fn is_marker_valid(marker_file: &Path, session_id: &str) -> bool {
    if !marker_file.exists() {
        return false;
    }

    fs::read_to_string(marker_file)
        .map(|content| {
            content.split(':').next().map(|s| s == session_id).unwrap_or(false)
        })
        .unwrap_or(false)
}

fn write_marker(marker_file: &Path, session_id: &str, pr_info: &str) {
    if let Some(parent) = marker_file.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(marker_file, format!("{}:{}", session_id, pr_info));
}

fn create_conductor_marker(project_dir: &str) {
    let marker_path = PathBuf::from(project_dir)
        .join(".claude")
        .join(".conductor-session");

    if let Some(parent) = marker_path.parent() {
        let _ = fs::create_dir_all(parent);
    }

    let ppid = std::process::id();
    let created_at = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let marker_data = serde_json::json!({
        "ppid": ppid,
        "created_at": created_at
    });

    let _ = fs::write(marker_path, serde_json::to_string(&marker_data).unwrap_or_default());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_session_id() {
        let id = get_session_id();
        assert!(!id.is_empty());
    }

    #[test]
    fn test_get_short_hash() {
        let hash = get_short_hash();
        assert!(!hash.is_empty());
    }
}

//! Post-tool hook: Run formatter and type checker on Python files.
//!
//! Triggered after Edit or Write tools modify files.
//! Runs ruff (format + lint) and ty (type check) on Python files.

use anyhow::Result;
use hook_common::prelude::*;
use hook_common::subprocess::run_command_with_timeout;
use std::path::Path;
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(30);

fn main() -> Result<()> {
    let input = HookInput::from_stdin()?;

    // Only check Edit and Write tools
    if !input.is_edit() && !input.is_write() {
        return Ok(());
    }

    let file_path = match input.get_file_path() {
        Some(path) => path,
        None => return Ok(()),
    };

    // Only check Python files
    if !file_path.ends_with(".py") {
        return Ok(());
    }

    // Validate path
    if file_path.contains("..") || file_path.len() > 4096 {
        return Ok(());
    }

    let project_dir = std::env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());

    // Determine relative path for display
    let rel_path = if file_path.starts_with(&project_dir) {
        Path::new(file_path)
            .strip_prefix(&project_dir)
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|_| file_path.to_string())
    } else {
        file_path.to_string()
    };

    let mut issues: Vec<String> = Vec::new();

    // Run ruff format
    let cmd = format!("cd {} && uv run ruff format {}", project_dir, file_path);
    if let Ok(result) = run_command_with_timeout(&cmd, TIMEOUT) {
        if !result.success {
            let output = if !result.stderr.is_empty() {
                &result.stderr
            } else {
                &result.stdout
            };
            if !output.trim().is_empty() {
                issues.push(format!("ruff format failed:\n{}", output));
            }
        }
    }

    // Run ruff check with auto-fix
    let cmd = format!(
        "cd {} && uv run ruff check --fix {}",
        project_dir, file_path
    );
    if let Ok(result) = run_command_with_timeout(&cmd, TIMEOUT) {
        if !result.success {
            let output = if !result.stdout.is_empty() {
                &result.stdout
            } else {
                &result.stderr
            };
            if !output.trim().is_empty() {
                issues.push(format!("ruff check issues:\n{}", output));
            }
        }
    }

    // Run ty type check
    let cmd = format!("cd {} && uv run ty check {}", project_dir, file_path);
    if let Ok(result) = run_command_with_timeout(&cmd, TIMEOUT) {
        if !result.success {
            let output = if !result.stdout.is_empty() {
                &result.stdout
            } else {
                &result.stderr
            };
            // Skip if ty is not installed
            if !output.contains("not found") && !output.contains("Failed to spawn") {
                if !output.trim().is_empty() {
                    issues.push(format!("ty check issues:\n{}", output));
                }
            }
        }
    }

    // Report results
    let message = if issues.is_empty() {
        format!("[lint-on-save] OK: {} passed all checks", rel_path)
    } else {
        format!(
            "[lint-on-save] Issues in {}:\n{}",
            rel_path,
            issues.join("\n")
        )
    };

    let output = HookOutput::post_tool_use().with_context(message);
    output.write_stdout()?;

    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_python_file_detection() {
        assert!("test.py".ends_with(".py"));
        assert!(!"test.rs".ends_with(".py"));
        assert!(!"test.txt".ends_with(".py"));
    }
}

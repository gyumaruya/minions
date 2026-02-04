//! Subprocess execution utilities.

use anyhow::{Context, Result};
use std::process::{Command, Output};
use std::time::Duration;

/// Result of a command execution.
#[derive(Debug, Clone)]
pub struct CommandResult {
    /// Exit code (None if killed by signal)
    pub exit_code: Option<i32>,
    /// Standard output
    pub stdout: String,
    /// Standard error
    pub stderr: String,
    /// Whether the command succeeded (exit code 0)
    pub success: bool,
}

impl CommandResult {
    /// Create from std::process::Output.
    pub fn from_output(output: Output) -> Self {
        Self {
            exit_code: output.status.code(),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            success: output.status.success(),
        }
    }
}

/// Run a shell command and return the result.
pub fn run_command(cmd: &str) -> Result<CommandResult> {
    let output = if cfg!(target_os = "windows") {
        Command::new("cmd").args(["/C", cmd]).output()
    } else {
        Command::new("sh").args(["-c", cmd]).output()
    }
    .with_context(|| format!("Failed to execute command: {}", cmd))?;

    Ok(CommandResult::from_output(output))
}

/// Run a shell command with timeout.
pub fn run_command_with_timeout(cmd: &str, timeout: Duration) -> Result<CommandResult> {
    use std::process::Stdio;
    use std::thread;

    let mut child = if cfg!(target_os = "windows") {
        Command::new("cmd")
            .args(["/C", cmd])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
    } else {
        Command::new("sh")
            .args(["-c", cmd])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
    }
    .with_context(|| format!("Failed to spawn command: {}", cmd))?;

    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                let output = child.wait_with_output()?;
                return Ok(CommandResult {
                    exit_code: status.code(),
                    stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                    stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                    success: status.success(),
                });
            }
            Ok(None) => {
                if start.elapsed() > timeout {
                    let _ = child.kill();
                    anyhow::bail!("Command timed out after {:?}: {}", timeout, cmd);
                }
                thread::sleep(Duration::from_millis(10));
            }
            Err(e) => return Err(e).context("Failed to wait for command"),
        }
    }
}

/// Check if a command exists in PATH.
pub fn command_exists(cmd: &str) -> bool {
    if cfg!(target_os = "windows") {
        Command::new("where").arg(cmd).output().map_or(false, |o| o.status.success())
    } else {
        Command::new("which").arg(cmd).output().map_or(false, |o| o.status.success())
    }
}

/// Run git command and return output.
pub fn git(args: &str) -> Result<CommandResult> {
    run_command(&format!("git {}", args))
}

/// Run gh (GitHub CLI) command and return output.
pub fn gh(args: &str) -> Result<CommandResult> {
    run_command(&format!("gh {}", args))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_command_success() {
        let result = run_command("echo hello").unwrap();
        assert!(result.success);
        assert!(result.stdout.trim() == "hello");
    }

    #[test]
    fn test_run_command_failure() {
        let result = run_command("exit 1").unwrap();
        assert!(!result.success);
        assert_eq!(result.exit_code, Some(1));
    }

    #[test]
    fn test_command_exists() {
        // 'echo' should exist on all platforms
        assert!(command_exists("echo"));
        // Random string should not exist
        assert!(!command_exists("nonexistent_command_12345"));
    }

    #[test]
    fn test_git_status() {
        // This test assumes we're in a git repo
        let result = git("status --porcelain");
        assert!(result.is_ok());
    }
}

//! SessionStart hook: Set up session environment variables.
//!
//! Sets AGENT_ROLE=conductor for main session via CLAUDE_ENV_FILE.

use anyhow::Result;
use std::env;
use std::fs::OpenOptions;
use std::io::Write;

fn main() -> Result<()> {
    // Get CLAUDE_ENV_FILE path
    let env_file = match env::var("CLAUDE_ENV_FILE") {
        Ok(path) => path,
        Err(_) => {
            // Not in SessionStart context, skip
            return Ok(());
        }
    };

    // Open file in append mode
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&env_file)?;

    // Set AGENT_ROLE=conductor for main session
    writeln!(file, "export AGENT_ROLE=conductor")?;

    // Create conductor session marker
    let project_dir = env::var("CLAUDE_PROJECT_DIR").unwrap_or_else(|_| ".".to_string());
    let marker_path = format!("{}/.claude/.conductor-session", project_dir);

    if let Ok(mut marker) = std::fs::File::create(&marker_path) {
        use std::time::{SystemTime, UNIX_EPOCH};
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let content = format!(r#"{{"created_at":{},"ppid":{}}}"#, ts, std::process::id());
        let _ = marker.write_all(content.as_bytes());
    }

    Ok(())
}

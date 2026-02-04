//! JSONL storage for memory events.

use crate::schema::{MemoryEvent, MemoryScope, MemoryType};
use anyhow::{Context, Result, anyhow};
use camino::Utf8PathBuf;
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};

/// JSONL-based memory storage.
#[derive(Debug, Clone)]
pub struct MemoryStorage {
    /// Path to the JSONL file
    path: Utf8PathBuf,
}

impl MemoryStorage {
    /// Create a new storage instance.
    pub fn new(path: impl Into<Utf8PathBuf>) -> Self {
        Self { path: path.into() }
    }

    /// Get default storage path.
    ///
    /// Priority:
    /// 1. AI_MEMORY_PATH environment variable (if set)
    /// 2. OS config directory (from `dirs::config_dir()`)
    /// 3. Error if neither is available
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - AI_MEMORY_PATH is not set
    /// - OS config directory cannot be determined (no HOME or XDG_CONFIG_HOME)
    pub fn default_path() -> Result<Utf8PathBuf> {
        // Priority 1: Allow override via environment variable
        if let Ok(custom_path) = std::env::var("AI_MEMORY_PATH") {
            return Ok(Utf8PathBuf::from(custom_path));
        }

        // Priority 2: Use OS config directory (XDG_CONFIG_HOME on Linux, ~/Library/Application Support on macOS, etc.)
        if let Some(config_dir) = dirs::config_dir() {
            if let Ok(utf8_path) = Utf8PathBuf::try_from(config_dir) {
                let memory_dir = utf8_path.join("ai/memory/events.jsonl");
                return Ok(memory_dir);
            }
        }

        // No valid path found
        Err(anyhow!(
            "Failed to determine memory storage path. Please set one of:\n  \
            1. Environment variable: AI_MEMORY_PATH=/path/to/events.jsonl\n  \
            2. Environment variable: HOME (for config directory resolution)\n  \
            3. Environment variable: XDG_CONFIG_HOME (on Linux)"
        ))
    }

    /// Ensure storage directory exists.
    pub fn ensure_dir(&self) -> Result<()> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)
                .with_context(|| format!("Failed to create directory: {}", parent))?;
        }
        Ok(())
    }

    /// Append a memory event to storage.
    pub fn append(&self, event: &MemoryEvent) -> Result<()> {
        self.ensure_dir()?;

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .with_context(|| format!("Failed to open storage: {}", self.path))?;

        let line = serde_json::to_string(event)?;
        writeln!(file, "{}", line)?;
        Ok(())
    }

    /// Load all memory events from storage.
    pub fn load_all(&self) -> Result<Vec<MemoryEvent>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }

        let file = fs::File::open(&self.path)
            .with_context(|| format!("Failed to open storage: {}", self.path))?;

        let reader = BufReader::new(file);
        let mut events = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<MemoryEvent>(&line) {
                Ok(event) => events.push(event),
                Err(e) => {
                    // Log error but continue
                    eprintln!("Warning: Failed to parse memory event: {}", e);
                }
            }
        }

        Ok(events)
    }

    /// Load memories filtered by type.
    pub fn load_by_type(&self, memory_type: MemoryType) -> Result<Vec<MemoryEvent>> {
        let all = self.load_all()?;
        Ok(all
            .into_iter()
            .filter(|e| e.memory_type == memory_type)
            .collect())
    }

    /// Load memories filtered by scope.
    pub fn load_by_scope(&self, scope: MemoryScope) -> Result<Vec<MemoryEvent>> {
        let all = self.load_all()?;
        Ok(all.into_iter().filter(|e| e.scope == scope).collect())
    }

    /// Search memories by content (simple substring match).
    pub fn search(&self, query: &str) -> Result<Vec<MemoryEvent>> {
        let query_lower = query.to_lowercase();
        let all = self.load_all()?;
        Ok(all
            .into_iter()
            .filter(|e| {
                e.content.to_lowercase().contains(&query_lower)
                    || e.context.to_lowercase().contains(&query_lower)
                    || e.tags.iter().any(|t| t.to_lowercase().contains(&query_lower))
            })
            .collect())
    }

    /// Get recent memories (last N).
    pub fn recent(&self, limit: usize) -> Result<Vec<MemoryEvent>> {
        let mut all = self.load_all()?;
        if all.len() > limit {
            all = all.split_off(all.len() - limit);
        }
        Ok(all)
    }

    /// Count total memories.
    pub fn count(&self) -> Result<usize> {
        Ok(self.load_all()?.len())
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::AgentType;
    use std::env;
    use tempfile::tempdir;

    #[test]
    fn test_append_and_load() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.jsonl");
        let storage = MemoryStorage::new(Utf8PathBuf::from_path_buf(path).unwrap());

        let event = MemoryEvent::new(
            "Test memory",
            MemoryType::Observation,
            MemoryScope::User,
            AgentType::Claude,
        );

        storage.append(&event).unwrap();

        let loaded = storage.load_all().unwrap();
        assert_eq!(loaded.len(), 1);
        assert_eq!(loaded[0].content, "Test memory");
    }

    #[test]
    fn test_search() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.jsonl");
        let storage = MemoryStorage::new(Utf8PathBuf::from_path_buf(path).unwrap());

        storage
            .append(&MemoryEvent::new(
                "PRは日本語で書く",
                MemoryType::Preference,
                MemoryScope::User,
                AgentType::System,
            ))
            .unwrap();

        storage
            .append(&MemoryEvent::new(
                "テストを先に書く",
                MemoryType::Workflow,
                MemoryScope::User,
                AgentType::System,
            ))
            .unwrap();

        let results = storage.search("日本語").unwrap();
        assert_eq!(results.len(), 1);
        assert!(results[0].content.contains("日本語"));
    }

    #[test]
    fn test_load_by_type() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.jsonl");
        let storage = MemoryStorage::new(Utf8PathBuf::from_path_buf(path).unwrap());

        storage
            .append(&MemoryEvent::new(
                "Pref 1",
                MemoryType::Preference,
                MemoryScope::User,
                AgentType::System,
            ))
            .unwrap();

        storage
            .append(&MemoryEvent::new(
                "Workflow 1",
                MemoryType::Workflow,
                MemoryScope::User,
                AgentType::System,
            ))
            .unwrap();

        let prefs = storage.load_by_type(MemoryType::Preference).unwrap();
        assert_eq!(prefs.len(), 1);
        assert_eq!(prefs[0].content, "Pref 1");
    }

    #[test]
    fn test_default_path_with_env() {
        let dir = tempdir().unwrap();
        let test_path = dir.path().join("test.jsonl");
        let test_path_str = test_path.to_string_lossy().to_string();

        // Set AI_MEMORY_PATH
        unsafe {
            env::set_var("AI_MEMORY_PATH", &test_path_str);
        }
        let result = MemoryStorage::default_path();
        unsafe {
            env::remove_var("AI_MEMORY_PATH");
        }

        assert!(result.is_ok());
        assert_eq!(result.unwrap().to_string(), test_path_str);
    }

    #[test]
    fn test_default_path_fallback_to_dirs() {
        // Verify that when AI_MEMORY_PATH is not set, we get a valid path or error
        // (depending on whether dirs::config_dir() works)
        unsafe {
            env::remove_var("AI_MEMORY_PATH");
        }

        let result = MemoryStorage::default_path();

        // Should either succeed (if OS config dir is available) or return a clear error
        match result {
            Ok(path) => {
                // Path should contain 'ai/memory/events.jsonl'
                assert!(path.to_string().contains("ai/memory/events.jsonl"));
            }
            Err(e) => {
                // Error should mention the required environment variables
                let msg = e.to_string();
                assert!(
                    msg.contains("AI_MEMORY_PATH") || msg.contains("HOME") || msg.contains("XDG_CONFIG_HOME"),
                    "Error message should mention required env vars: {}",
                    msg
                );
            }
        }
    }

    #[test]
    fn test_storage_with_custom_path() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("custom/nested/test.jsonl");
        let storage = MemoryStorage::new(Utf8PathBuf::from_path_buf(path).unwrap());

        let event = MemoryEvent::new(
            "Custom path test",
            MemoryType::Observation,
            MemoryScope::Session,
            AgentType::Claude,
        );

        // Ensure directory creation works for nested paths
        storage.append(&event).unwrap();

        let loaded = storage.load_all().unwrap();
        assert_eq!(loaded.len(), 1);
        assert_eq!(loaded[0].content, "Custom path test");
    }
}

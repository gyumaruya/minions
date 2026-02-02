//! State file management for hooks.

use anyhow::{Context, Result};
use serde::{de::DeserializeOwned, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// Manager for hook state files in /tmp.
#[derive(Debug, Clone)]
pub struct StateManager {
    /// Base directory for state files
    base_dir: PathBuf,
    /// Prefix for state file names
    prefix: String,
}

impl StateManager {
    /// Create a new state manager with the given prefix.
    pub fn new(prefix: impl Into<String>) -> Self {
        Self {
            base_dir: PathBuf::from("/tmp"),
            prefix: prefix.into(),
        }
    }

    /// Get the path for a state file with the given key.
    pub fn state_path(&self, key: &str) -> PathBuf {
        self.base_dir.join(format!("{}-{}.json", self.prefix, key))
    }

    /// Load state from file.
    pub fn load<T: DeserializeOwned>(&self, key: &str) -> Result<Option<T>> {
        let path = self.state_path(key);
        if !path.exists() {
            return Ok(None);
        }

        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read state file: {}", path.display()))?;

        let state: T = serde_json::from_str(&content)
            .with_context(|| format!("Failed to parse state file: {}", path.display()))?;

        Ok(Some(state))
    }

    /// Save state to file.
    pub fn save<T: Serialize>(&self, key: &str, state: &T) -> Result<()> {
        let path = self.state_path(key);
        let content = serde_json::to_string_pretty(state)?;
        fs::write(&path, content)
            .with_context(|| format!("Failed to write state file: {}", path.display()))?;
        Ok(())
    }

    /// Delete state file.
    pub fn delete(&self, key: &str) -> Result<()> {
        let path = self.state_path(key);
        if path.exists() {
            fs::remove_file(&path)
                .with_context(|| format!("Failed to delete state file: {}", path.display()))?;
        }
        Ok(())
    }

    /// Check if state file exists.
    pub fn exists(&self, key: &str) -> bool {
        self.state_path(key).exists()
    }

    /// Check if state file is older than the given duration.
    pub fn is_stale(&self, key: &str, max_age: Duration) -> bool {
        let path = self.state_path(key);
        if !path.exists() {
            return true;
        }

        match fs::metadata(&path) {
            Ok(metadata) => match metadata.modified() {
                Ok(modified) => {
                    let age = SystemTime::now()
                        .duration_since(modified)
                        .unwrap_or(Duration::MAX);
                    age > max_age
                }
                Err(_) => true,
            },
            Err(_) => true,
        }
    }

    /// Load state, or create default if missing or stale.
    pub fn load_or_default<T>(&self, key: &str, max_age: Duration) -> Result<T>
    where
        T: DeserializeOwned + Default + Serialize,
    {
        if self.is_stale(key, max_age) {
            let default = T::default();
            self.save(key, &default)?;
            return Ok(default);
        }

        match self.load(key)? {
            Some(state) => Ok(state),
            None => {
                let default = T::default();
                self.save(key, &default)?;
                Ok(default)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::{Deserialize, Serialize};
    use tempfile::tempdir;

    #[derive(Debug, Default, Serialize, Deserialize, PartialEq)]
    struct TestState {
        counter: u32,
        message: String,
    }

    #[test]
    fn test_save_and_load() {
        let dir = tempdir().unwrap();
        let manager = StateManager {
            base_dir: dir.path().to_path_buf(),
            prefix: "test".to_string(),
        };

        let state = TestState {
            counter: 42,
            message: "hello".to_string(),
        };

        manager.save("key1", &state).unwrap();
        let loaded: Option<TestState> = manager.load("key1").unwrap();
        assert_eq!(loaded, Some(state));
    }

    #[test]
    fn test_load_missing() {
        let dir = tempdir().unwrap();
        let manager = StateManager {
            base_dir: dir.path().to_path_buf(),
            prefix: "test".to_string(),
        };

        let loaded: Option<TestState> = manager.load("nonexistent").unwrap();
        assert_eq!(loaded, None);
    }

    #[test]
    fn test_delete() {
        let dir = tempdir().unwrap();
        let manager = StateManager {
            base_dir: dir.path().to_path_buf(),
            prefix: "test".to_string(),
        };

        let state = TestState::default();
        manager.save("key1", &state).unwrap();
        assert!(manager.exists("key1"));

        manager.delete("key1").unwrap();
        assert!(!manager.exists("key1"));
    }
}

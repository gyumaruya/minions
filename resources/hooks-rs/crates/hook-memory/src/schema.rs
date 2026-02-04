//! Memory schema - unified format for multi-agent memory system.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Memory visibility scope.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MemoryScope {
    /// Current session only
    Session,
    /// User-wide, persistent
    User,
    /// Specific agent only
    Agent,
    /// Shared across all agents
    Public,
}

/// Type of memory event.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MemoryType {
    /// Factual observation
    Observation,
    /// Design/implementation decision
    Decision,
    /// Future plan or intent
    Plan,
    /// Code, file, or output reference
    Artifact,
    /// User preference
    Preference,
    /// Workflow pattern
    Workflow,
    /// Error pattern and solution
    Error,
    /// Research finding
    Research,
}

/// Agent identifiers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentType {
    Claude,
    Codex,
    Gemini,
    Copilot,
    System,
}

/// Unified memory event schema.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEvent {
    /// Unique identifier
    pub id: String,

    /// Memory content
    pub content: String,

    /// Type of memory
    pub memory_type: MemoryType,

    /// Visibility scope
    pub scope: MemoryScope,

    /// Source agent
    pub source_agent: AgentType,

    /// Additional context
    #[serde(default)]
    pub context: String,

    /// Confidence score (0.0 to 1.0)
    #[serde(default = "default_confidence")]
    pub confidence: f64,

    /// Time to live in days (None = permanent)
    #[serde(default)]
    pub ttl_days: Option<u32>,

    /// Tags for categorization
    #[serde(default)]
    pub tags: Vec<String>,

    /// Additional metadata
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,

    /// Creation timestamp (ISO 8601)
    pub created_at: String,
}

fn default_confidence() -> f64 {
    1.0
}

impl MemoryEvent {
    /// Create a new memory event.
    pub fn new(
        content: impl Into<String>,
        memory_type: MemoryType,
        scope: MemoryScope,
        source_agent: AgentType,
    ) -> Self {
        let now = chrono_now();
        Self {
            id: generate_id(),
            content: content.into(),
            memory_type,
            scope,
            source_agent,
            context: String::new(),
            confidence: 1.0,
            ttl_days: None,
            tags: Vec::new(),
            metadata: HashMap::new(),
            created_at: now,
        }
    }

    /// Set context.
    pub fn with_context(mut self, context: impl Into<String>) -> Self {
        self.context = context.into();
        self
    }

    /// Set confidence.
    pub fn with_confidence(mut self, confidence: f64) -> Self {
        self.confidence = confidence.clamp(0.0, 1.0);
        self
    }

    /// Set TTL.
    pub fn with_ttl(mut self, days: u32) -> Self {
        self.ttl_days = Some(days);
        self
    }

    /// Add tag.
    pub fn with_tag(mut self, tag: impl Into<String>) -> Self {
        self.tags.push(tag.into());
        self
    }
}

/// Generate a unique ID based on timestamp.
fn generate_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    format!("{}{:06}", duration.as_secs(), duration.subsec_micros())
}

/// Get current time in ISO 8601 format.
fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = duration.as_secs();
    // Simple ISO 8601 format (without timezone)
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}",
        1970 + secs / 31536000,
        (secs % 31536000) / 2592000 + 1,
        (secs % 2592000) / 86400 + 1,
        (secs % 86400) / 3600,
        (secs % 3600) / 60,
        secs % 60
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memory_event_creation() {
        let event = MemoryEvent::new(
            "Test memory",
            MemoryType::Observation,
            MemoryScope::User,
            AgentType::Claude,
        );
        assert_eq!(event.content, "Test memory");
        assert_eq!(event.memory_type, MemoryType::Observation);
        assert_eq!(event.confidence, 1.0);
    }

    #[test]
    fn test_memory_event_builder() {
        let event = MemoryEvent::new(
            "Preference",
            MemoryType::Preference,
            MemoryScope::User,
            AgentType::System,
        )
        .with_context("User said")
        .with_confidence(0.9)
        .with_tag("pr")
        .with_tag("japanese");

        assert_eq!(event.context, "User said");
        assert_eq!(event.confidence, 0.9);
        assert_eq!(event.tags, vec!["pr", "japanese"]);
    }

    #[test]
    fn test_serialization() {
        let event = MemoryEvent::new(
            "Test",
            MemoryType::Decision,
            MemoryScope::Session,
            AgentType::Codex,
        );
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("\"memory_type\":\"decision\""));
        assert!(json.contains("\"scope\":\"session\""));
    }
}

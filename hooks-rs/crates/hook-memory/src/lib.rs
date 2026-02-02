//! Memory system for Claude Code hooks.
//!
//! Provides:
//! - Memory event schema
//! - JSONL storage
//! - Basic scoring

pub mod schema;
pub mod storage;

pub use schema::{AgentType, MemoryEvent, MemoryScope, MemoryType};
pub use storage::MemoryStorage;

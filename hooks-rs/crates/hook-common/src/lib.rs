//! Common utilities for Claude Code hooks.
//!
//! This crate provides shared functionality for all Rust-based hooks:
//! - JSON input/output parsing
//! - Subprocess execution
//! - State file management
//! - Error handling

pub mod input;
pub mod output;
pub mod state;
pub mod subprocess;

pub use input::{HookInput, ToolInput};
pub use output::{HookOutput, PermissionDecision};
pub use state::StateManager;
pub use subprocess::run_command;

/// Re-export commonly used types
pub mod prelude {
    pub use crate::input::{HookInput, ToolInput};
    pub use crate::output::{HookOutput, PermissionDecision};
    pub use crate::state::StateManager;
    pub use crate::subprocess::run_command;
    pub use anyhow::{Context, Result};
    pub use serde::{Deserialize, Serialize};
}

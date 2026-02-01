"""
Permission hierarchy for agent delegation.

Implements automatic permission inheritance where parent agents
can grant permissions to child agents without manual approval.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PermissionScope(str, Enum):
    """Scope of permission grants."""

    # File operations
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    EDIT_FILES = "edit_files"

    # Command execution
    BASH_SAFE = "bash_safe"  # Safe commands (git, npm, etc.)
    BASH_WRITE = "bash_write"  # Commands that modify files
    BASH_NETWORK = "bash_network"  # Network operations

    # Agent operations
    SPAWN_SUBAGENT = "spawn_subagent"
    DELEGATE_TASK = "delegate_task"

    # External tools
    USE_CODEX = "use_codex"
    USE_GEMINI = "use_gemini"
    USE_COPILOT = "use_copilot"

    # All permissions
    ALL = "all"


@dataclass
class PermissionGrant:
    """
    A permission grant from parent to child agent.

    When a parent agent spawns a child, it can grant specific
    permissions that the child can use without additional prompts.
    """

    scope: PermissionScope
    granted_by: str  # Agent ID that granted this permission
    constraints: dict[str, Any] = field(default_factory=dict)
    # Optional expiration (in seconds from grant time)
    ttl_seconds: int | None = None

    def to_cli_flags(self) -> list[str]:
        """Convert permission to Claude Code CLI flags."""
        scope_to_flags: dict[PermissionScope, list[str]] = {
            PermissionScope.READ_FILES: ["--allowedTools", "Read,Glob,Grep"],
            PermissionScope.WRITE_FILES: ["--allowedTools", "Write"],
            PermissionScope.EDIT_FILES: ["--allowedTools", "Edit"],
            PermissionScope.BASH_SAFE: [
                "--allowedTools",
                "Bash(git:*),Bash(jj:*),Bash(npm:*)",
            ],
            PermissionScope.BASH_WRITE: ["--allowedTools", "Bash"],
            PermissionScope.BASH_NETWORK: ["--allowedTools", "Bash(curl:*),WebFetch"],
            PermissionScope.SPAWN_SUBAGENT: ["--allowedTools", "Task"],
            PermissionScope.DELEGATE_TASK: ["--allowedTools", "Task"],
            PermissionScope.USE_CODEX: ["--allowedTools", "Bash(codex:*)"],
            PermissionScope.USE_GEMINI: ["--allowedTools", "Bash(gemini:*)"],
            PermissionScope.USE_COPILOT: ["--allowedTools", "Bash(copilot:*)"],
            PermissionScope.ALL: ["--dangerouslySkipPermissions"],
        }
        return scope_to_flags.get(self.scope, [])


@dataclass
class PermissionSet:
    """Collection of permissions for an agent."""

    grants: list[PermissionGrant] = field(default_factory=list)

    def add(self, grant: PermissionGrant) -> None:
        """Add a permission grant."""
        self.grants.append(grant)

    def has_permission(self, scope: PermissionScope) -> bool:
        """Check if a specific permission is granted."""
        return any(
            g.scope == scope or g.scope == PermissionScope.ALL for g in self.grants
        )

    def to_cli_flags(self) -> list[str]:
        """Convert all permissions to CLI flags."""
        # Check for ALL permission first
        if self.has_permission(PermissionScope.ALL):
            return ["--dangerouslySkipPermissions"]

        # Collect all flags
        flags: list[str] = []
        for grant in self.grants:
            flags.extend(grant.to_cli_flags())
        return flags


# Default permission sets for each role
CONDUCTOR_PERMISSIONS = PermissionSet(
    grants=[
        PermissionGrant(scope=PermissionScope.ALL, granted_by="system"),
    ]
)

SECTION_LEADER_PERMISSIONS = PermissionSet(
    grants=[
        PermissionGrant(scope=PermissionScope.READ_FILES, granted_by="conductor"),
        PermissionGrant(scope=PermissionScope.SPAWN_SUBAGENT, granted_by="conductor"),
        PermissionGrant(scope=PermissionScope.DELEGATE_TASK, granted_by="conductor"),
        PermissionGrant(scope=PermissionScope.USE_CODEX, granted_by="conductor"),
        PermissionGrant(scope=PermissionScope.USE_GEMINI, granted_by="conductor"),
        PermissionGrant(scope=PermissionScope.USE_COPILOT, granted_by="conductor"),
    ]
)

MUSICIAN_PERMISSIONS = PermissionSet(
    grants=[
        PermissionGrant(scope=PermissionScope.READ_FILES, granted_by="section_leader"),
        PermissionGrant(scope=PermissionScope.WRITE_FILES, granted_by="section_leader"),
        PermissionGrant(scope=PermissionScope.EDIT_FILES, granted_by="section_leader"),
        PermissionGrant(scope=PermissionScope.BASH_SAFE, granted_by="section_leader"),
    ]
)

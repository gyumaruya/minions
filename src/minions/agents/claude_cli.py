"""
Claude Code CLI wrapper for spawning subagents.

Provides a programmatic interface to invoke Claude Code CLI
with proper permission inheritance and hierarchy context.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from minions.agents.base import AgentHierarchy, AgentPersona, AgentRole
from minions.agents.permissions import PermissionGrant, PermissionScope, PermissionSet


@dataclass
class ClaudeCodeResult:
    """Result from Claude Code CLI execution."""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaudeCodeRunner:
    """
    Wrapper for invoking Claude Code CLI.

    Handles:
    - Permission inheritance from parent agent
    - Persona injection into prompts
    - Hierarchy context propagation
    - Output capture and parsing
    """

    # Working directory for CLI execution
    working_dir: Path | None = None

    # Default model for subagents
    default_model: str = "sonnet"

    # Timeout in seconds
    timeout: int = 300

    # Whether to use print mode (non-interactive)
    print_mode: bool = True

    def spawn_subagent(
        self,
        prompt: str,
        *,
        parent: AgentHierarchy,
        role: AgentRole = AgentRole.MUSICIAN,
        persona: AgentPersona | None = None,
        permissions: PermissionSet | None = None,
        model: str | None = None,
        additional_context: str = "",
    ) -> ClaudeCodeResult:
        """
        Spawn a subagent with inherited permissions.

        Args:
            prompt: The task prompt for the subagent
            parent: Parent agent hierarchy info
            role: Role of the new subagent
            persona: Optional persona override
            permissions: Optional permission set (inherits from parent if None)
            model: Optional model override
            additional_context: Additional context to inject

        Returns:
            ClaudeCodeResult with output and status
        """
        # Build the full prompt with hierarchy context
        full_prompt = self._build_prompt(
            prompt=prompt,
            parent=parent,
            role=role,
            persona=persona,
            additional_context=additional_context,
        )

        # Determine permissions
        if permissions is None:
            permissions = self._inherit_permissions(parent)

        # Build CLI command
        cmd = self._build_command(
            prompt=full_prompt,
            permissions=permissions,
            model=model or self.default_model,
        )

        # Execute
        return self._execute(cmd)

    def run_direct(
        self,
        prompt: str,
        *,
        permissions: PermissionSet | None = None,
        model: str | None = None,
    ) -> ClaudeCodeResult:
        """
        Run Claude Code directly without hierarchy context.

        Useful for simple one-off commands.
        """
        if permissions is None:
            permissions = PermissionSet()

        cmd = self._build_command(
            prompt=prompt,
            permissions=permissions,
            model=model or self.default_model,
        )

        return self._execute(cmd)

    def _build_prompt(
        self,
        prompt: str,
        parent: AgentHierarchy,
        role: AgentRole,
        persona: AgentPersona | None,
        additional_context: str,
    ) -> str:
        """Build full prompt with hierarchy and persona context."""
        parts = []

        # Add hierarchy context
        parts.append("# Subagent Context")
        parts.append(f"Parent Agent: {parent.agent_id} ({parent.role.value})")
        parts.append(f"Your Role: {role.value}")
        parts.append("")

        # Add persona if provided
        if persona:
            parts.append(persona.to_prompt())
            parts.append("")

        # Add hierarchy rules
        parts.append("## Hierarchy Rules")
        parts.append("- Report results back to parent agent")
        parts.append("- Do not interact directly with user")
        parts.append("- Stay within granted permission scope")
        parts.append("- Complete task and return concise summary")
        parts.append("")

        # Add additional context
        if additional_context:
            parts.append("## Additional Context")
            parts.append(additional_context)
            parts.append("")

        # Add the actual task
        parts.append("## Task")
        parts.append(prompt)

        return "\n".join(parts)

    def _inherit_permissions(self, parent: AgentHierarchy) -> PermissionSet:
        """Inherit permissions from parent based on role."""
        # Conductor can grant all permissions
        if parent.role == AgentRole.CONDUCTOR:
            return PermissionSet(
                grants=[
                    PermissionGrant(
                        scope=PermissionScope.ALL, granted_by=parent.agent_id
                    ),
                ]
            )

        # Section Leader grants limited permissions
        if parent.role == AgentRole.SECTION_LEADER:
            return PermissionSet(
                grants=[
                    PermissionGrant(
                        scope=PermissionScope.READ_FILES, granted_by=parent.agent_id
                    ),
                    PermissionGrant(
                        scope=PermissionScope.WRITE_FILES, granted_by=parent.agent_id
                    ),
                    PermissionGrant(
                        scope=PermissionScope.EDIT_FILES, granted_by=parent.agent_id
                    ),
                    PermissionGrant(
                        scope=PermissionScope.BASH_SAFE, granted_by=parent.agent_id
                    ),
                ]
            )

        # Musicians can't spawn subagents by default
        return PermissionSet()

    def _build_command(
        self,
        prompt: str,
        permissions: PermissionSet,
        model: str,
    ) -> list[str]:
        """Build the claude CLI command."""
        cmd = ["claude"]

        # Add print mode flag
        if self.print_mode:
            cmd.append("--print")

        # Add model
        cmd.extend(["--model", model])

        # Add permission flags
        permission_flags = permissions.to_cli_flags()
        cmd.extend(permission_flags)

        # Add prompt
        cmd.extend(["--prompt", prompt])

        return cmd

    def _execute(self, cmd: list[str]) -> ClaudeCodeResult:
        """Execute the CLI command and capture output."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_dir,
            )

            return ClaudeCodeResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                metadata={"command": " ".join(cmd)},
            )

        except subprocess.TimeoutExpired:
            return ClaudeCodeResult(
                success=False,
                output="",
                error=f"Command timed out after {self.timeout} seconds",
                exit_code=-1,
                metadata={"command": " ".join(cmd), "timeout": True},
            )

        except FileNotFoundError:
            return ClaudeCodeResult(
                success=False,
                output="",
                error="claude command not found. Install with: npm install -g @anthropic-ai/claude-code",
                exit_code=-1,
                metadata={"command": " ".join(cmd), "not_found": True},
            )

        except Exception as e:
            return ClaudeCodeResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                metadata={"command": " ".join(cmd), "exception": type(e).__name__},
            )


def create_conductor_runner(working_dir: Path | None = None) -> ClaudeCodeRunner:
    """Create a runner configured for Conductor-level operations."""
    return ClaudeCodeRunner(
        working_dir=working_dir,
        default_model="opus",  # Conductor uses best model
        timeout=600,  # Longer timeout for complex tasks
        print_mode=True,
    )


def create_musician_runner(working_dir: Path | None = None) -> ClaudeCodeRunner:
    """Create a runner configured for Musician-level operations."""
    return ClaudeCodeRunner(
        working_dir=working_dir,
        default_model="sonnet",  # Musicians use faster model
        timeout=300,
        print_mode=True,
    )

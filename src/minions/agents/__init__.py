"""
Hierarchical Multi-Agent System for Claude Code Orchestra.

Inspired by multi-agent-shogun's feudal Japanese hierarchy,
adapted to an orchestra metaphor:

- Conductor: Overall orchestration, user interaction
- SectionLeader: Task management, distribution
- Musician: Task execution (subagents)

The hierarchy allows parent agents to delegate permissions to children,
eliminating the need for manual permission prompts.
"""

from minions.agents.base import (
    AgentHierarchy,
    AgentPersona,
    AgentRole,
)
from minions.agents.claude_cli import ClaudeCodeRunner
from minions.agents.permissions import PermissionGrant, PermissionScope

__all__ = [
    "AgentHierarchy",
    "AgentPersona",
    "AgentRole",
    "ClaudeCodeRunner",
    "PermissionGrant",
    "PermissionScope",
]

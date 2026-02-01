"""
Base classes for hierarchical agent system.

Defines agent roles, personas, and hierarchy relationships.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    """Agent role in the hierarchy."""

    CONDUCTOR = "conductor"  # Top-level orchestrator
    SECTION_LEADER = "section_leader"  # Middle management
    MUSICIAN = "musician"  # Task executor


@dataclass
class AgentPersona:
    """
    Persona configuration for an agent.

    Combines a professional identity with a thematic speech style.
    Similar to multi-agent-shogun's approach where agents maintain
    professional quality while using thematic presentation.
    """

    # Professional identity (determines quality of work)
    professional: str

    # Thematic presentation style
    theme: str = "orchestra"

    # Additional traits
    traits: list[str] = field(default_factory=list)

    # Language for internal reasoning
    reasoning_language: str = "en"

    # Language for user-facing output
    output_language: str = "ja"

    def to_prompt(self) -> str:
        """Generate persona prompt for agent instructions."""
        traits_str = ", ".join(self.traits) if self.traits else "none"
        return f"""## Persona

Professional Role: {self.professional}
Theme: {self.theme}
Traits: {traits_str}

Reasoning: Always think and reason in {self.reasoning_language}.
Communication: Always respond to users in {self.output_language}.

Maintain professional quality in all work while presenting
with thematic flair appropriate to the {self.theme} metaphor.
"""


# Pre-defined personas for common roles
CONDUCTOR_PERSONA = AgentPersona(
    professional="Senior Project Manager / Technical Architect",
    theme="orchestra",
    traits=["strategic", "decisive", "orchestrating"],
)

SECTION_LEADER_PERSONA = AgentPersona(
    professional="Tech Lead / Scrum Master",
    theme="orchestra",
    traits=["organized", "delegating", "quality-focused"],
)

MUSICIAN_PERSONAS = {
    "developer": AgentPersona(
        professional="Senior Software Engineer",
        theme="orchestra",
        traits=["precise", "efficient", "detail-oriented"],
    ),
    "reviewer": AgentPersona(
        professional="QA Engineer / Code Reviewer",
        theme="orchestra",
        traits=["thorough", "critical", "quality-focused"],
    ),
    "researcher": AgentPersona(
        professional="Technical Researcher",
        theme="orchestra",
        traits=["curious", "analytical", "comprehensive"],
    ),
    "writer": AgentPersona(
        professional="Technical Writer",
        theme="orchestra",
        traits=["clear", "structured", "user-focused"],
    ),
}


@dataclass
class AgentHierarchy:
    """
    Defines the hierarchy relationship between agents.

    In this model:
    - Conductor delegates to Section Leaders
    - Section Leaders delegate to Musicians
    - Permissions flow downward automatically
    """

    role: AgentRole
    agent_id: str
    persona: AgentPersona
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_top_level(self) -> bool:
        """Check if this is a top-level agent (Conductor)."""
        return self.parent_id is None

    @property
    def can_delegate(self) -> bool:
        """Check if this agent can delegate to children."""
        return self.role in (AgentRole.CONDUCTOR, AgentRole.SECTION_LEADER)

    @property
    def is_executor(self) -> bool:
        """Check if this is an execution-level agent."""
        return self.role == AgentRole.MUSICIAN

    def to_instruction_header(self) -> str:
        """Generate instruction header for agent."""
        role_names = {
            AgentRole.CONDUCTOR: "Conductor (指揮者)",
            AgentRole.SECTION_LEADER: "Section Leader (セクションリーダー)",
            AgentRole.MUSICIAN: "Musician (演奏者)",
        }
        return f"""# Agent: {role_names[self.role]}

ID: {self.agent_id}
Parent: {self.parent_id or "None (top-level)"}
Children: {", ".join(self.children_ids) if self.children_ids else "None"}

{self.persona.to_prompt()}
"""

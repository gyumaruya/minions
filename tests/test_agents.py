"""
Tests for the hierarchical agent system.
"""

import pytest

from minions.agents.base import (
    CONDUCTOR_PERSONA,
    MUSICIAN_PERSONAS,
    SECTION_LEADER_PERSONA,
    AgentHierarchy,
    AgentPersona,
    AgentRole,
)
from minions.agents.permissions import (
    CONDUCTOR_PERMISSIONS,
    MUSICIAN_PERMISSIONS,
    SECTION_LEADER_PERMISSIONS,
    PermissionGrant,
    PermissionScope,
    PermissionSet,
)


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_role_values(self) -> None:
        assert AgentRole.CONDUCTOR.value == "conductor"
        assert AgentRole.SECTION_LEADER.value == "section_leader"
        assert AgentRole.MUSICIAN.value == "musician"


class TestAgentPersona:
    """Tests for AgentPersona."""

    def test_persona_creation(self) -> None:
        persona = AgentPersona(
            professional="Senior Engineer",
            theme="orchestra",
            traits=["precise", "efficient"],
        )
        assert persona.professional == "Senior Engineer"
        assert persona.theme == "orchestra"
        assert "precise" in persona.traits

    def test_persona_to_prompt(self) -> None:
        persona = AgentPersona(
            professional="Tech Lead",
            theme="orchestra",
            traits=["organized"],
        )
        prompt = persona.to_prompt()
        assert "Tech Lead" in prompt
        assert "orchestra" in prompt
        assert "organized" in prompt

    def test_predefined_personas(self) -> None:
        assert CONDUCTOR_PERSONA.professional is not None
        assert SECTION_LEADER_PERSONA.professional is not None
        assert "developer" in MUSICIAN_PERSONAS


class TestAgentHierarchy:
    """Tests for AgentHierarchy."""

    def test_conductor_is_top_level(self) -> None:
        conductor = AgentHierarchy(
            role=AgentRole.CONDUCTOR,
            agent_id="conductor-1",
            persona=CONDUCTOR_PERSONA,
            parent_id=None,
        )
        assert conductor.is_top_level
        assert conductor.can_delegate
        assert not conductor.is_executor

    def test_section_leader_has_parent(self) -> None:
        section_leader = AgentHierarchy(
            role=AgentRole.SECTION_LEADER,
            agent_id="section-1",
            persona=SECTION_LEADER_PERSONA,
            parent_id="conductor-1",
        )
        assert not section_leader.is_top_level
        assert section_leader.can_delegate
        assert not section_leader.is_executor

    def test_musician_is_executor(self) -> None:
        musician = AgentHierarchy(
            role=AgentRole.MUSICIAN,
            agent_id="musician-1",
            persona=MUSICIAN_PERSONAS["developer"],
            parent_id="section-1",
        )
        assert not musician.is_top_level
        assert not musician.can_delegate
        assert musician.is_executor

    def test_instruction_header(self) -> None:
        conductor = AgentHierarchy(
            role=AgentRole.CONDUCTOR,
            agent_id="conductor-1",
            persona=CONDUCTOR_PERSONA,
        )
        header = conductor.to_instruction_header()
        assert "Conductor" in header
        assert "conductor-1" in header


class TestPermissionScope:
    """Tests for PermissionScope enum."""

    def test_scope_values(self) -> None:
        assert PermissionScope.READ_FILES.value == "read_files"
        assert PermissionScope.WRITE_FILES.value == "write_files"
        assert PermissionScope.ALL.value == "all"


class TestPermissionGrant:
    """Tests for PermissionGrant."""

    def test_grant_creation(self) -> None:
        grant = PermissionGrant(
            scope=PermissionScope.READ_FILES,
            granted_by="conductor-1",
        )
        assert grant.scope == PermissionScope.READ_FILES
        assert grant.granted_by == "conductor-1"

    def test_grant_to_cli_flags(self) -> None:
        grant = PermissionGrant(
            scope=PermissionScope.ALL,
            granted_by="system",
        )
        flags = grant.to_cli_flags()
        assert "--dangerouslySkipPermissions" in flags


class TestPermissionSet:
    """Tests for PermissionSet."""

    def test_empty_permission_set(self) -> None:
        pset = PermissionSet()
        assert not pset.has_permission(PermissionScope.READ_FILES)

    def test_add_permission(self) -> None:
        pset = PermissionSet()
        pset.add(
            PermissionGrant(scope=PermissionScope.READ_FILES, granted_by="test")
        )
        assert pset.has_permission(PermissionScope.READ_FILES)

    def test_all_permission_grants_everything(self) -> None:
        pset = PermissionSet(
            grants=[PermissionGrant(scope=PermissionScope.ALL, granted_by="system")]
        )
        assert pset.has_permission(PermissionScope.READ_FILES)
        assert pset.has_permission(PermissionScope.WRITE_FILES)
        assert pset.has_permission(PermissionScope.BASH_WRITE)

    def test_predefined_permission_sets(self) -> None:
        assert CONDUCTOR_PERMISSIONS.has_permission(PermissionScope.ALL)
        assert SECTION_LEADER_PERMISSIONS.has_permission(PermissionScope.READ_FILES)
        assert MUSICIAN_PERMISSIONS.has_permission(PermissionScope.EDIT_FILES)


class TestHierarchyIntegration:
    """Integration tests for the hierarchy system."""

    def test_full_hierarchy_chain(self) -> None:
        # Create conductor
        conductor = AgentHierarchy(
            role=AgentRole.CONDUCTOR,
            agent_id="conductor-1",
            persona=CONDUCTOR_PERSONA,
            children_ids=["section-1"],
        )

        # Create section leader
        section_leader = AgentHierarchy(
            role=AgentRole.SECTION_LEADER,
            agent_id="section-1",
            persona=SECTION_LEADER_PERSONA,
            parent_id="conductor-1",
            children_ids=["musician-1", "musician-2"],
        )

        # Create musicians
        musician_1 = AgentHierarchy(
            role=AgentRole.MUSICIAN,
            agent_id="musician-1",
            persona=MUSICIAN_PERSONAS["developer"],
            parent_id="section-1",
        )

        musician_2 = AgentHierarchy(
            role=AgentRole.MUSICIAN,
            agent_id="musician-2",
            persona=MUSICIAN_PERSONAS["reviewer"],
            parent_id="section-1",
        )

        # Verify hierarchy
        assert conductor.is_top_level
        assert section_leader.parent_id == conductor.agent_id
        assert musician_1.parent_id == section_leader.agent_id
        assert musician_2.parent_id == section_leader.agent_id

        # Verify delegation capabilities
        assert conductor.can_delegate
        assert section_leader.can_delegate
        assert not musician_1.can_delegate
        assert not musician_2.can_delegate

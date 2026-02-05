"""
Integration tests for memory system.

Tests the full flow:
- Hook triggers → memory saved → memory searchable → memory loaded
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from minions.memory import (
    AgentType,
    MemoryBroker,
    MemoryScope,
    MemoryType,
)


class TestMemoryCLI:
    """Test memory CLI commands."""

    def test_cli_add_and_search(self, tmp_path: Path) -> None:
        """Test adding and searching via CLI."""
        # Set up environment
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        # Create memory directory
        memory_dir = tmp_path / "minions" / ".claude" / "memory"
        memory_dir.mkdir(parents=True)

        cli_path = (
            Path(__file__).parent.parent / "src" / "minions" / "memory" / "cli.py"
        )

        # Add a memory
        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "add",
                "Test preference",
                "--type",
                "preference",
                "--context",
                "test",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "Memory saved" in result.stdout

        # Search for it
        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "search",
                "Test",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "Test preference" in result.stdout

    def test_cli_stats(self, tmp_path: Path) -> None:
        """Test stats command."""
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        memory_dir = tmp_path / "minions" / ".claude" / "memory"
        memory_dir.mkdir(parents=True)

        cli_path = (
            Path(__file__).parent.parent / "src" / "minions" / "memory" / "cli.py"
        )

        result = subprocess.run(
            [sys.executable, str(cli_path), "stats"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "Total memories" in result.stdout

    def test_cli_json_output(self, tmp_path: Path) -> None:
        """Test JSON output mode."""
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        memory_dir = tmp_path / "minions" / ".claude" / "memory"
        memory_dir.mkdir(parents=True)

        cli_path = (
            Path(__file__).parent.parent / "src" / "minions" / "memory" / "cli.py"
        )

        # Add a memory
        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "--json",
                "add",
                "JSON test",
                "--type",
                "preference",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["content"] == "JSON test"
        assert data["memory_type"] == "preference"


class TestAutoLearnHook:
    """Test auto-learn hook."""

    def test_detect_correction_pattern(self) -> None:
        """Test detection of correction patterns."""
        # Import the hook module
        hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "auto-learn.py"

        # Load module dynamically
        import importlib.util

        spec = importlib.util.spec_from_file_location("auto_learn", hook_path)
        assert spec is not None
        assert spec.loader is not None
        auto_learn = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auto_learn)

        # Test correction patterns
        learnings = auto_learn.detect_learning("PRは日本語にして")
        assert len(learnings) == 1
        assert learnings[0][1] == "user_correction"

        learnings = auto_learn.detect_learning("コミットメッセージに変えて")
        assert len(learnings) == 1
        assert learnings[0][1] == "user_correction"

        learnings = auto_learn.detect_learning("いつもテストを先に書く")
        assert len(learnings) == 1
        assert learnings[0][1] == "workflow"

    def test_no_detection_for_normal_text(self) -> None:
        """Test that normal text doesn't trigger learning."""
        hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "auto-learn.py"

        import importlib.util

        spec = importlib.util.spec_from_file_location("auto_learn", hook_path)
        assert spec is not None
        assert spec.loader is not None
        auto_learn = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auto_learn)

        learnings = auto_learn.detect_learning("こんにちは")
        assert len(learnings) == 0

        learnings = auto_learn.detect_learning("ファイルを読んで")
        assert len(learnings) == 0


class TestLoadMemoriesHook:
    """Test load-memories hook."""

    def test_format_memories(self) -> None:
        """Test memory formatting for context injection."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "load-memories.py"
        )

        import importlib.util

        spec = importlib.util.spec_from_file_location("load_memories", hook_path)
        assert spec is not None
        assert spec.loader is not None
        load_memories = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(load_memories)

        memories = [
            {"memory_type": "preference", "content": "日本語で書く"},
            {"memory_type": "workflow", "content": "テスト先に書く"},
            {"memory_type": "error", "content": "エラー解決策"},
        ]

        formatted = load_memories.format_memories_for_context(memories)

        assert "記憶から読み込んだ情報" in formatted
        assert "ユーザーの好み" in formatted
        assert "日本語で書く" in formatted
        assert "ワークフロー" in formatted
        assert "テスト先に書く" in formatted

    def test_empty_memories(self) -> None:
        """Test handling of empty memories."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "load-memories.py"
        )

        import importlib.util

        spec = importlib.util.spec_from_file_location("load_memories", hook_path)
        assert spec is not None
        assert spec.loader is not None
        load_memories = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(load_memories)

        formatted = load_memories.format_memories_for_context([])
        assert formatted == ""


class TestEndToEndFlow:
    """Test end-to-end memory flow."""

    def test_full_flow(self, tmp_path: Path) -> None:
        """Test complete flow: save → search → retrieve."""
        # Create broker with temp directory
        broker = MemoryBroker(base_dir=tmp_path, enable_mem0=False)

        # 1. Save a preference (simulating auto-learn)
        event = broker.add(
            content="コードは英語で書く",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
            context="auto-learn: user_preference",
        )
        assert event.id is not None

        # 2. Save a workflow
        broker.remember_workflow(
            "コミット後は自動でPR作成",
            trigger="コミット完了時",
        )

        # 3. Save an error pattern
        broker.remember_error(
            error="jj describe メールエラー",
            solution="noreply メール使用",
        )

        # 4. Search for preferences
        results = broker.search(
            query="英語",
            memory_type=MemoryType.PREFERENCE,
            limit=5,
        )
        assert len(results) == 1
        assert "コードは英語で書く" in results[0].content

        # 5. Get relevant memories (simulating session start)
        prefs = broker.search(
            query="",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            limit=5,
            use_semantic=False,
        )
        assert len(prefs) >= 1

        workflows = broker.search(
            query="",
            memory_type=MemoryType.WORKFLOW,
            limit=3,
            use_semantic=False,
        )
        assert len(workflows) >= 1

        errors = broker.search(
            query="",
            memory_type=MemoryType.ERROR,
            limit=3,
            use_semantic=False,
        )
        assert len(errors) >= 1

        # 6. Check stats
        stats = broker.get_stats()
        assert stats["total_events"] >= 3
        assert "preference" in stats["by_type"]
        assert "workflow" in stats["by_type"]
        assert "error" in stats["by_type"]

    def test_sensitive_data_redaction(self, tmp_path: Path) -> None:
        """Test that sensitive data is redacted."""
        broker = MemoryBroker(base_dir=tmp_path, enable_mem0=False)

        # Try to save memory with API key
        event = broker.add(
            content="Use API key sk-proj-abc123xyz",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
        )

        # API key should be redacted
        assert "sk-proj" not in event.content
        assert "[REDACTED]" in event.content

    def test_memory_persistence(self, tmp_path: Path) -> None:
        """Test that memories persist across broker instances."""
        # Create first broker and save memory
        broker1 = MemoryBroker(base_dir=tmp_path, enable_mem0=False)
        broker1.add(
            content="永続化テスト",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.USER,
            source_agent=AgentType.CLAUDE,
        )

        # Create second broker instance
        broker2 = MemoryBroker(base_dir=tmp_path, enable_mem0=False)

        # Search should find the memory
        results = broker2.search("永続化", limit=5)
        assert len(results) == 1
        assert "永続化テスト" in results[0].content

#!/usr/bin/env python3
"""Configuration utilities for Claude Code hooks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_project_dir() -> Path:
    """Get the project directory."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def load_config() -> dict[str, Any]:
    """Load configuration from .claude/config.json."""
    config_path = get_project_dir() / ".claude" / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_agent_enabled(agent: str) -> bool:
    """Check if an agent (codex/gemini/copilot) is enabled."""
    config = load_config()
    agents = config.get("agents", {})
    agent_config = agents.get(agent, {})
    return agent_config.get("enabled", True)  # Default: enabled


def get_agent_command(agent: str) -> str:
    """Get the command for an agent."""
    config = load_config()
    agents = config.get("agents", {})
    agent_config = agents.get(agent, {})
    return agent_config.get("command", agent)


def get_openai_api_key() -> str | None:
    """
    Get OpenAI API key with cross-platform support.

    Priority:
    1. Environment variable (OPENAI_API_KEY or configured)
    2. macOS Keychain (if enabled and on macOS)
    """
    config = load_config()
    platform_config = config.get("platform", {})

    # 1. Try environment variable first
    env_var = platform_config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(env_var)
    if api_key:
        return api_key

    # 2. Try macOS Keychain if enabled
    use_keychain = platform_config.get("use_keychain", True)
    if use_keychain and sys.platform == "darwin":
        try:
            username = os.environ.get("USER", "")
            if not username:
                return None
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a",
                    username,
                    "-s",
                    "openai-api-key",
                    "-w",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

    return None

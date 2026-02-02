#!/usr/bin/env python3
"""
Hook: Record tool execution results to memory.

Records tool executions (Bash, Edit, Write, etc.) with automatic
importance scoring for the self-improvement memory cycle.

Phase: RECORD
Trigger: PostToolUse
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Tools worth recording (significant actions)
RECORDABLE_TOOLS = {
    "Bash": True,
    "Edit": True,
    "Write": True,
    "Task": True,
    "WebFetch": True,
    "WebSearch": True,
}

# Tools to skip (read-only, low value for learning)
SKIP_TOOLS = {
    "Read": True,
    "Glob": True,
    "Grep": True,
    "LS": True,
}


# Maximum content length to record.
# 500 characters is a compromise between capturing enough detail for
# useful self-improvement memories and keeping each record small so
# that storage/memory usage stays bounded. Adjust with care if memory
# backends or storage limits change.
MAX_CONTENT_LENGTH = 500


def get_openai_api_key_from_keychain() -> str | None:
    """Get OpenAI API key from macOS Keychain."""
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

        if result.returncode == 0:
            api_key = result.stdout.strip()
            return api_key if api_key else None

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return None


def truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Truncate content to max length with ellipsis."""
    if len(content) <= max_length:
        return content
    return content[: max_length - 3] + "..."


def extract_tool_summary(tool_name: str, tool_input: dict, tool_output: str) -> str:
    """Extract a meaningful summary from tool execution."""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Get first line of command
        first_line = command.split("\n")[0][:100]
        success = (
            "error" not in tool_output.lower() and "failed" not in tool_output.lower()
        )
        return f"Command: {first_line} -> {'Success' if success else 'Failed'}"

    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "unknown")
        return f"Edited: {Path(file_path).name}"

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "unknown")
        return f"Created: {Path(file_path).name}"

    elif tool_name == "Task":
        prompt = tool_input.get("prompt", "")[:100]
        subagent = tool_input.get("subagent_type", "unknown")
        return f"Task ({subagent}): {prompt}"

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "unknown")
        return f"Fetched: {url}"

    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return f"Searched: {query}"

    return f"{tool_name} execution"


def determine_success(tool_name: str, tool_output: str) -> bool:
    """Determine if tool execution was successful."""
    output_lower = tool_output.lower()

    # Common failure indicators
    failure_indicators = [
        "error:",
        "failed",
        "exception",
        "traceback",
        "permission denied",
        "not found",
        "command not found",
    ]

    for indicator in failure_indicators:
        if indicator in output_lower:
            return False

    return True


def record_tool_result(
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    execution_time_ms: int | None = None,
) -> bool:
    """Record tool result to memory."""
    try:
        from minions.memory import AgentType, MemoryBroker, MemoryScope, MemoryType
        from minions.memory.scoring import ScoringContext

        # Try to get API key from Keychain
        api_key = get_openai_api_key_from_keychain()
        enable_mem0 = False

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            enable_mem0 = True

        broker = MemoryBroker(enable_mem0=enable_mem0)

        # Extract summary
        summary = extract_tool_summary(tool_name, tool_input, tool_output)
        success = determine_success(tool_name, tool_output)

        # Create scoring context
        scoring_ctx = ScoringContext(
            tool_name=tool_name,
            tool_success=success,
            execution_time_ms=execution_time_ms,
            session_id=os.environ.get("CLAUDE_SESSION_ID"),
        )

        # Build content
        content = f"Tool: {tool_name}\n{summary}"
        if not success:
            # Include error details for failures
            error_preview = truncate_content(tool_output, 200)
            content = f"[FAILURE] {content}\nError: {error_preview}"

        # Build metadata
        metadata = {
            "tool_name": tool_name,
            "outcome": "success" if success else "failure",
            "execution_time_ms": execution_time_ms,
        }

        # Add relevant input details
        if tool_name == "Bash":
            metadata["command"] = truncate_content(tool_input.get("command", ""), 200)
        elif tool_name in ("Edit", "Write"):
            metadata["file_path"] = tool_input.get("file_path", "")

        broker.add(
            content=content,
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.SESSION,
            source_agent=AgentType.CLAUDE,
            context=f"tool:{tool_name}",
            metadata=metadata,
            scoring_context=scoring_ctx,
        )

        return True

    except Exception as e:
        print(f"[post-tool-record] Error: {e}", file=sys.stderr)
        return False


def main() -> None:
    """Main hook entry point."""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Get tool information
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_output = hook_input.get("tool_output", "")

    # Skip non-recordable tools
    if tool_name in SKIP_TOOLS:
        sys.exit(0)

    if tool_name not in RECORDABLE_TOOLS:
        sys.exit(0)

    # Note: Tool execution time should come from external source, not hook processing time
    execution_time_ms = None

    # Record the result
    success = record_tool_result(tool_name, tool_input, tool_output, execution_time_ms)

    if success:
        # Output minimal feedback
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "",  # Silent recording
                }
            },
            sys.stdout,
            ensure_ascii=False,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()

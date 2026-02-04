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
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from config_utils import get_openai_api_key

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


def infer_memory_type(
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    success: bool,
) -> str:
    """
    Infer appropriate memory type from tool execution context.

    Priority:
    1. ERROR - Failed tool executions
    2. DECISION - Design/architecture related tasks
    3. WORKFLOW - Successful task sequences
    4. OBSERVATION - Default for everything else
    """
    from minions.memory import MemoryType

    # Priority 1: ERROR - Failed executions
    if not success:
        return MemoryType.ERROR.value

    # Priority 2: DECISION - Design/architecture tasks
    if tool_name == "Task":
        prompt = tool_input.get("prompt", "").lower()
        decision_keywords = [
            "design",
            "architecture",
            "decide",
            "choice",
            "approach",
            "trade-off",
            "codex",
            "gemini",
            "should i",
            "which",
            "better",
        ]
        if any(kw in prompt for kw in decision_keywords):
            return MemoryType.DECISION.value

    # Priority 3: WORKFLOW - Successful task sequences
    if tool_name == "Bash":
        command = tool_input.get("command", "").lower()
        workflow_patterns = [
            "ruff check",
            "ruff format",
            "ty check",
            "pytest",
            "git commit",
            "git push",
            "uv run",
        ]
        if any(pattern in command for pattern in workflow_patterns):
            return MemoryType.WORKFLOW.value

    # Default: OBSERVATION
    return MemoryType.OBSERVATION.value


def _extract_error_context(tool_name: str, tool_input: dict) -> str:
    """Extract context information for error memories."""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Get first line of command
        first_line = command.split("\n")[0]
        return f"Command: {first_line}"
    elif tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "")
        return f"File: {file_path}"
    return f"Tool: {tool_name}"


def _extract_workflow_pattern(tool_name: str, tool_input: dict) -> str:
    """Extract workflow pattern for successful sequences."""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Identify the pattern
        if "ruff check" in command and "ruff format" in command:
            return "Lint + Format"
        elif "pytest" in command:
            return "Test execution"
        elif "git commit" in command:
            return "Git commit"
        elif "uv run" in command:
            return "UV command execution"
        return "Bash command"
    return f"{tool_name} execution"


def _extract_decision_context(tool_input: dict) -> str:
    """Extract decision context from Task tool input."""
    prompt = tool_input.get("prompt", "")
    # Get first 150 characters
    preview = prompt[:150]
    if len(prompt) > 150:
        preview += "..."
    return preview


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
        api_key = get_openai_api_key()
        enable_mem0 = False

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            enable_mem0 = True

        broker = MemoryBroker(enable_mem0=enable_mem0)

        # Extract summary
        summary = extract_tool_summary(tool_name, tool_input, tool_output)
        success = determine_success(tool_name, tool_output)

        # Infer memory type
        memory_type_value = infer_memory_type(
            tool_name, tool_input, tool_output, success
        )

        # Create scoring context
        scoring_ctx = ScoringContext(
            tool_name=tool_name,
            tool_success=success,
            execution_time_ms=execution_time_ms,
            session_id=os.environ.get("CLAUDE_SESSION_ID"),
        )

        # Build content with structured information
        if not success:
            # ERROR type: Include detailed failure information
            error_preview = truncate_content(tool_output, 300)
            content = f"""[FAILURE] Tool: {tool_name}
{summary}

Error: {error_preview}

Context: {_extract_error_context(tool_name, tool_input)}"""
        elif memory_type_value == MemoryType.WORKFLOW.value:
            # WORKFLOW type: Include successful pattern
            content = f"""[SUCCESS] Workflow: {tool_name}
{summary}

Pattern: {_extract_workflow_pattern(tool_name, tool_input)}"""
        elif memory_type_value == MemoryType.DECISION.value:
            # DECISION type: Include decision context
            content = f"""[DECISION] Tool: {tool_name}
{summary}

Context: {_extract_decision_context(tool_input)}"""
        else:
            # OBSERVATION: Default format
            content = f"Tool: {tool_name}\n{summary}"

        # Build metadata
        metadata = {
            "tool_name": tool_name,
            "outcome": "success" if success else "failure",
            "execution_time_ms": execution_time_ms,
            "memory_type": memory_type_value,
        }

        # Add relevant input details
        if tool_name == "Bash":
            metadata["command"] = truncate_content(tool_input.get("command", ""), 200)
        elif tool_name in ("Edit", "Write"):
            metadata["file_path"] = tool_input.get("file_path", "")
        elif tool_name == "Task":
            metadata["subagent_type"] = tool_input.get("subagent_type", "unknown")

        # Determine scope based on memory type
        scope = MemoryScope.SESSION
        if memory_type_value in (MemoryType.DECISION.value, MemoryType.WORKFLOW.value):
            scope = MemoryScope.USER  # Decisions and workflows are user-scoped

        broker.add(
            content=content,
            memory_type=MemoryType(memory_type_value),
            scope=scope,
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

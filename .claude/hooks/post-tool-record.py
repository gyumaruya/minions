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


def redact_sensitive_data(text: str) -> str:
    """Redact sensitive data from text."""
    import re

    if not text:
        return text

    patterns = [
        # API Keys (OpenAI, Anthropic, etc.)
        (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "[REDACTED_API_KEY]"),
        (re.compile(r"sk-proj-[a-zA-Z0-9_-]{32,}"), "[REDACTED_API_KEY]"),
        # AWS
        (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
        (re.compile(r"[a-zA-Z0-9/+=]{40}(?=\s|$)"), "[REDACTED_AWS_SECRET]"),
        # GitHub tokens (flexible length)
        (re.compile(r"ghp_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
        (re.compile(r"gho_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
        (re.compile(r"ghs_[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
        # Generic secrets
        (
            re.compile(
                r"(api[_-]?key|apikey|secret|password|token)\s*[=:]\s*['\"]?([^\s'\"]+)",
                re.IGNORECASE,
            ),
            r"\1=[REDACTED]",
        ),
        # JWT tokens
        (
            re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
            "[REDACTED_JWT]",
        ),
    ]

    result = text
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)
    return result


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


def determine_success(
    tool_name: str, tool_output: str, tool_input: dict = None
) -> bool:
    """
    Determine if tool execution was successful.

    Priority:
    1. Exit code (if available in tool_input)
    2. Explicit outcome field
    3. Error indicators in output
    """
    # Priority 1: Exit code (if available)
    if tool_input and "exit_code" in tool_input:
        return tool_input["exit_code"] == 0

    output_lower = tool_output.lower()

    # Priority 2: Positive indicators (handle double negatives)
    positive_indicators = [
        "no error",
        "no errors",
        "success",
        "passed",
        "ok",
        "completed",
    ]

    # If we see positive indicators, check if they're NOT negated
    for indicator in positive_indicators:
        if indicator in output_lower:
            # Check for negation patterns nearby
            idx = output_lower.find(indicator)
            context_before = output_lower[max(0, idx - 20) : idx]
            if not any(
                neg in context_before for neg in ["not", "no", "n't", "without"]
            ):
                return True

    # Priority 3: Error indicators (failure)
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

    # Default: Assume success if no clear failure
    return True


def _is_user_correction(context: str, tool_input: dict) -> bool:
    """Detect user correction patterns."""
    import re

    correction_patterns = [
        r"にして",
        r"に変えて",
        r"は違う",
        r"がいい",
        r"いつも",
        r"毎回",
        r"覚えて[:：]",
    ]

    text = context + str(tool_input)
    return any(re.search(p, text) for p in correction_patterns)


def _is_design_decision(tool_name: str, tool_input: dict, context: str) -> bool:
    """
    Detect design decisions (strict to reduce false positives).

    Returns True only for:
    - Codex/Gemini consultations (non-trivial)
    - Task tool with design-related keywords (multi-word phrases)
    """
    # Codex/Gemini consultations are likely decisions
    if tool_name in ["codex", "gemini"]:
        prompt = str(tool_input.get("prompt", ""))
        # Exclude simple execution commands
        if "exec" in prompt and len(prompt) < 50:
            return False
        return True

    # Task tool with design keywords
    if tool_name == "Task":
        task_prompt = str(tool_input.get("prompt", "")).lower()

        # Multi-word phrases to reduce false positives
        decision_phrases = [
            "design",
            "architecture",
            "should we",
            "should i",
            "which approach",
            "trade-off",
            "better than",
            "choose between",
            "how to implement",
        ]

        # Require actual phrase match (not just "which")
        return any(phrase in task_prompt for phrase in decision_phrases)

    return False


def _is_workflow_pattern(tool_name: str, tool_input: dict, success: bool) -> bool:
    """Detect successful workflow patterns."""
    if not success:
        return False

    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        workflow_commands = [
            "ruff check",
            "ruff format",
            "ty check",
            "pytest",
            "git commit",
            "git push",
            "uv run",
        ]
        return any(cmd in command for cmd in workflow_commands)

    return False


def infer_memory_type_with_confidence(
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    success: bool,
    context: str = "",
) -> tuple[str, float]:
    """
    Infer memory type with confidence score.

    Returns:
        (memory_type, confidence): Memory type and confidence score (0.0-1.0)
    """

    scores = {
        "preference": 0.0,
        "workflow": 0.0,
        "decision": 0.0,
        "error": 0.0,
        "observation": 0.5,  # Default baseline
    }

    # 1. Preference detection (user corrections)
    if _is_user_correction(context, tool_input):
        scores["preference"] = 0.9

    # 2. Error detection (failures)
    if not success:
        scores["error"] = 0.95

    # 3. Decision detection (design/architecture, strict)
    if _is_design_decision(tool_name, tool_input, context):
        scores["decision"] = 0.8

    # 4. Workflow detection (successful patterns)
    if _is_workflow_pattern(tool_name, tool_input, success):
        scores["workflow"] = 0.7

    # Select highest scoring type
    memory_type = max(scores, key=scores.get)
    confidence = scores[memory_type]

    # Fallback to observation if confidence too low
    if confidence < 0.6:
        memory_type = "observation"
        confidence = 0.5

    return memory_type, confidence


def infer_memory_type(
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    success: bool,
    context: str = "",
) -> str:
    """
    Infer appropriate memory type from tool execution context.

    Uses confidence-based scoring to reduce false positives.
    """
    memory_type, _ = infer_memory_type_with_confidence(
        tool_name, tool_input, tool_output, success, context
    )
    return memory_type


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
        from minions.memory import AgentType, MemoryBroker, MemoryScope
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
        success = determine_success(tool_name, tool_output, tool_input)

        # Infer memory type with confidence
        memory_type_value, confidence = infer_memory_type_with_confidence(
            tool_name, tool_input, tool_output, success, context=""
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
        elif memory_type_value == "workflow":
            # WORKFLOW type: Include successful pattern
            content = f"""[SUCCESS] Workflow: {tool_name}
{summary}

Pattern: {_extract_workflow_pattern(tool_name, tool_input)}"""
        elif memory_type_value == "decision":
            # DECISION type: Include decision context
            content = f"""[DECISION] Tool: {tool_name}
{summary}

Context: {_extract_decision_context(tool_input)}"""
        elif memory_type_value == "preference":
            # PREFERENCE type: User correction/preference
            content = f"""[PREFERENCE] Tool: {tool_name}
{summary}

User feedback detected"""
        else:
            # OBSERVATION: Default format
            content = f"Tool: {tool_name}\n{summary}"

        # Redact sensitive data from content
        content = redact_sensitive_data(content)

        # Build metadata
        metadata = {
            "tool_name": tool_name,
            "outcome": "success" if success else "failure",
            "execution_time_ms": execution_time_ms,
            "memory_type": memory_type_value,
            "type_confidence": confidence,
        }

        # Add relevant input details (with redaction)
        if tool_name == "Bash":
            command = str(tool_input.get("command", ""))
            # Redact sensitive data from command
            command = redact_sensitive_data(command)
            metadata["command"] = truncate_content(command, 200)
        elif tool_name in ("Edit", "Write"):
            metadata["file_path"] = tool_input.get("file_path", "")
        elif tool_name == "Task":
            metadata["subagent_type"] = tool_input.get("subagent_type", "unknown")
            # Redact prompt if present
            if "prompt" in tool_input:
                prompt = str(tool_input.get("prompt", ""))
                metadata["prompt"] = redact_sensitive_data(
                    truncate_content(prompt, 200)
                )

        # Determine scope based on memory type
        scope = MemoryScope.SESSION
        if memory_type_value in ("decision", "workflow", "preference"):
            scope = (
                MemoryScope.USER
            )  # Decisions, workflows, and preferences are user-scoped

        broker.add(
            content=content,
            memory_type=memory_type_value,
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

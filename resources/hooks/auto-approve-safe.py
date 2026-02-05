#!/usr/bin/env python3
"""
PermissionRequest hook: Auto-approve safe commands, deny dangerous ones.

Strategy:
1. Deny clearly dangerous commands (system-wide destructive)
2. Allow project-scoped safe commands
3. Ask Haiku for ambiguous cases (with timeout & circuit breaker)
4. Log all decisions for audit trail
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

# ============================================================
# Configuration
# ============================================================

HAIKU_TIMEOUT = 2  # seconds
HAIKU_MAX_RETRIES = 1
CIRCUIT_BREAKER_THRESHOLD = 3  # failures before circuit opens
CIRCUIT_BREAKER_RESET_TIME = 60  # seconds

LOG_DIR = Path.home() / "minions" / ".claude" / "logs"
LOG_FILE = LOG_DIR / "permission-decisions.jsonl"

# Circuit breaker state (in-memory, per process)
_circuit_breaker = {
    "failures": 0,
    "last_failure": None,
    "state": "closed",  # closed, open, half_open
}


# ============================================================
# Helpers
# ============================================================


def log_decision(
    command: str,
    decision: Literal["allow", "deny", "ask_user"],
    reason: str,
    rule_id: str | None = None,
    confidence: float | None = None,
) -> None:
    """Log permission decision to audit trail."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "decision": decision,
        "reason": reason,
        "rule_id": rule_id,
        "confidence": confidence,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def allow(command: str, reason: str, rule_id: str | None = None) -> None:
    """Allow command and exit."""
    log_decision(command, "allow", reason, rule_id, confidence=1.0)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow", "message": f"✅ {reason}"},
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def deny(command: str, reason: str, rule_id: str | None = None) -> None:
    """Deny command and exit."""
    log_decision(command, "deny", reason, rule_id, confidence=1.0)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": f"⛔ {reason}"},
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def ask_user(command: str, reason: str) -> None:
    """Let user decide (no decision)."""
    log_decision(command, "ask_user", reason, confidence=0.5)
    sys.exit(0)


def parse_command(command: str) -> list[str]:
    """Parse command into tokens, handling shell syntax safely."""
    try:
        # Remove leading/trailing whitespace
        command = command.strip()

        # Detect bypass attempts
        bypass_patterns = [
            r"\$\(",  # Command substitution
            r"`",  # Backticks
            r"\beval\b",  # eval
            r"\bexec\b",  # exec
            r"\bsh\s+-c",  # sh -c
            r"\bbash\s+-c",  # bash -c
            r"base64.*decode",  # base64 decode
        ]

        for pattern in bypass_patterns:
            if re.search(pattern, command):
                return ["__BYPASS_DETECTED__", command]

        # Parse with shlex (safer than regex)
        tokens = shlex.split(command)
        return tokens

    except ValueError:
        # shlex parse failed (unmatched quotes, etc.)
        return ["__PARSE_ERROR__", command]


# ============================================================
# Dangerous Command Detection
# ============================================================

DANGEROUS_PATTERNS = {
    # System-wide destructive
    "rm_root": (r"^rm\s+.*-rf\s+/", "Deletes entire filesystem"),
    "rm_home": (r"^rm\s+.*-rf\s+~", "Deletes home directory"),
    "sudo_rm": (r"^sudo\s+rm", "Root-level file deletion"),
    "dd": (r"^dd\s+", "Disk destroyer"),
    "mkfs": (r"\bmkfs\b", "Filesystem formatting"),
    "fdisk": (r"\bfdisk\b", "Partition manipulation"),
    "disk_overwrite": (r">\s*/dev/sd", "Disk overwrite"),
    "fork_bomb": (r":\(\)\s*\{", "Fork bomb"),
    # System control
    "shutdown": (r"^shutdown\b", "System shutdown"),
    "reboot": (r"^reboot\b", "System reboot"),
    "halt": (r"^halt\b", "System halt"),
    "kill_all": (r"^kill\s+-9\s+-1", "Kill all processes"),
    # Network abuse
    "polling_curl": (r"^while.*curl", "Network polling/flooding"),
    "polling_wget": (r"^while.*wget", "Network polling/flooding"),
    "hping": (r"\bhping\b", "DoS tool"),
    # Package managers (global)
    "sudo_apt": (r"^sudo\s+apt", "Global package changes"),
    "sudo_yum": (r"^sudo\s+yum", "Global package changes"),
    "sudo_dnf": (r"^sudo\s+dnf", "Global package changes"),
    "brew_uninstall": (r"^brew\s+uninstall", "Global package removal"),
    # Dangerous redirects
    "etc_overwrite": (r">\s*/etc/", "System config overwrite"),
    "curl_pipe_bash": (r"curl.*\|\s*bash", "Remote code execution"),
    # Dangerous version control subcommands
    "git_clean_fdx": (
        r"^git\s+clean\s+.*-.*f.*d.*x",
        "Deletes untracked files forcefully",
    ),
    "git_reset_hard": (r"^git\s+reset\s+--hard\s+HEAD~", "Loses commit history"),
    "gh_repo_delete": (r"^gh\s+repo\s+delete", "Deletes repository"),
}


def is_dangerous(
    command: str, tokens: list[str]
) -> tuple[bool, str | None, str | None]:
    """Check if command is dangerous. Returns (is_dangerous, rule_id, reason)."""
    # Check bypass detection
    if tokens and tokens[0] == "__BYPASS_DETECTED__":
        return True, "bypass_detected", "Command contains shell injection patterns"

    if tokens and tokens[0] == "__PARSE_ERROR__":
        return True, "parse_error", "Command has malformed syntax (potential bypass)"

    # Check against dangerous patterns
    for rule_id, (pattern, description) in DANGEROUS_PATTERNS.items():
        if re.search(pattern, command, re.IGNORECASE):
            return True, rule_id, f"Dangerous: {description}"

    return False, None, None


# ============================================================
# Safe Command Detection (Project-scoped)
# ============================================================

SAFE_COMMANDS = {
    # Version control
    "git": {
        "allow": [
            "status",
            "diff",
            "log",
            "show",
            "branch",
            "checkout",
            "add",
            "commit",
            "push",
            "pull",
            "fetch",
        ],
        "deny": ["clean -fdx", "reset --hard HEAD~"],
    },
    "jj": {"allow": ["log", "status", "diff", "describe", "new", "bookmark"]},
    "gh": {
        "allow": ["pr", "issue", "status", "auth"],
        "deny": ["repo delete"],
    },
    # Testing & linting
    "pytest": {"allow": ["*"]},
    "ruff": {"allow": ["check", "format"]},
    "ty": {"allow": ["check"]},
    "mypy": {"allow": ["*"]},
    "eslint": {"allow": ["*"]},
    # Package managers (project-scoped)
    "uv": {"allow": ["*"]},
    "npm": {"allow": ["test", "run", "install", "ci"]},
    "pnpm": {"allow": ["test", "run", "install"]},
    "yarn": {"allow": ["test", "run", "install"]},
    "poetry": {"allow": ["*"]},
    # Build tools
    "make": {"allow": ["*"]},
    "cargo": {"allow": ["build", "test", "check", "run"]},
    "go": {"allow": ["build", "test", "run", "mod"]},
    # Task runners
    "poe": {"allow": ["*"]},
    "just": {"allow": ["*"]},
    # File operations (read-only or project-scoped)
    "ls": {"allow": ["*"]},
    "cat": {"allow": ["*"]},
    "grep": {"allow": ["*"]},
    "find": {"allow": ["*"]},
    "tree": {"allow": ["*"]},
    # Info commands
    "which": {"allow": ["*"]},
    "command": {"allow": ["-v"]},
    "python": {"allow": ["--version", "-c", "-m"]},
    "node": {"allow": ["--version"]},
    # Docker (project-scoped)
    "docker": {
        "allow": ["compose", "build", "run --rm"],
        "deny": ["rm -f", "system prune -af"],
    },
}


def is_safe_project(tokens: list[str]) -> tuple[bool, str | None]:
    """Check if command is safe project-scoped. Returns (is_safe, reason)."""
    if not tokens or tokens[0] in ["__BYPASS_DETECTED__", "__PARSE_ERROR__"]:
        return False, None

    base_cmd = tokens[0]

    if base_cmd not in SAFE_COMMANDS:
        return False, None

    rules = SAFE_COMMANDS[base_cmd]

    # Check deny list first
    if "deny" in rules:
        subcommand = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        for deny_pattern in rules["deny"]:
            if deny_pattern in subcommand:
                return False, f"Subcommand '{deny_pattern}' is dangerous"

    # Check allow list
    if "allow" in rules:
        allow_patterns = rules["allow"]
        if "*" in allow_patterns:
            return True, f"Project-scoped {base_cmd} command"

        subcommand = tokens[1] if len(tokens) > 1 else ""
        if subcommand in allow_patterns:
            return True, f"Safe {base_cmd} {subcommand}"

    return False, None


# ============================================================
# Haiku Consultation (with circuit breaker)
# ============================================================


def check_circuit_breaker() -> bool:
    """Check if circuit breaker is open. Returns True if requests should be blocked."""
    if _circuit_breaker["state"] == "open":
        last_failure = _circuit_breaker["last_failure"]
        if (
            last_failure
            and (datetime.now() - last_failure).total_seconds()
            < CIRCUIT_BREAKER_RESET_TIME
        ):
            return True  # Circuit still open
        else:
            _circuit_breaker["state"] = "half_open"  # Try again
            return False

    return False


def record_haiku_failure() -> None:
    """Record Haiku call failure and potentially open circuit."""
    _circuit_breaker["failures"] += 1
    _circuit_breaker["last_failure"] = datetime.now()

    if _circuit_breaker["failures"] >= CIRCUIT_BREAKER_THRESHOLD:
        _circuit_breaker["state"] = "open"


def record_haiku_success() -> None:
    """Record Haiku call success and close circuit."""
    _circuit_breaker["failures"] = 0
    _circuit_breaker["state"] = "closed"


def ask_haiku(command: str) -> tuple[Literal["allow", "deny", "uncertain"], float]:
    """Ask Haiku for judgment. Returns (decision, confidence)."""
    # Check circuit breaker
    if check_circuit_breaker():
        return "uncertain", 0.0

    prompt = f"""You are a security analyzer for command execution permissions.

Command to analyze:
```bash
{command}
```

Determine if this command is:
1. **SAFE** - Project-scoped, non-destructive, commonly used in development
2. **DANGEROUS** - System-wide destructive, irreversible, or security risk
3. **UNCERTAIN** - Not clearly safe or dangerous

Respond with ONLY ONE WORD and a confidence score (0.0-1.0):
- "allow 0.9" if SAFE with high confidence
- "deny 0.9" if DANGEROUS with high confidence
- "uncertain 0.3" if UNCERTAIN

Format: "<decision> <confidence>"
Example: "allow 0.85"

Your response:"""

    try:
        result = subprocess.run(
            ["claude", "--model", "claude-haiku-4", "--no-stream", "--silent"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=HAIKU_TIMEOUT,
        )

        if result.returncode != 0:
            record_haiku_failure()
            return "uncertain", 0.0

        response = result.stdout.strip().lower()

        # Parse response: "<decision> <confidence>"
        parts = response.split()
        decision = parts[0] if parts else "uncertain"
        confidence = float(parts[1]) if len(parts) > 1 else 0.5

        # Validate decision
        if decision not in ["allow", "deny", "uncertain"]:
            decision = "uncertain"
            confidence = 0.3

        record_haiku_success()
        return decision, confidence

    except subprocess.TimeoutExpired:
        record_haiku_failure()
        return "uncertain", 0.0
    except Exception:
        record_haiku_failure()
        return "uncertain", 0.0


# ============================================================
# Main Logic
# ============================================================


def main() -> None:
    # Read JSON input from stdin
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only process Bash tool
    if tool_name != "Bash":
        ask_user(command, "Non-Bash tool, user decides")

    # Parse command
    tokens = parse_command(command)

    # 1. Check if dangerous
    is_bad, rule_id, reason = is_dangerous(command, tokens)
    if is_bad:
        deny(command, reason, rule_id)

    # 2. Check if safe project-scoped
    is_good, reason = is_safe_project(tokens)
    if is_good:
        allow(command, reason, rule_id=tokens[0])

    # 3. Ask Haiku for ambiguous cases
    decision, confidence = ask_haiku(command)

    if decision == "allow" and confidence >= 0.7:
        log_decision(
            command,
            "allow",
            f"Haiku approved (confidence: {confidence})",
            "haiku",
            confidence,
        )
        allow(
            command, f"Haiku approved (confidence: {confidence:.0%})", rule_id="haiku"
        )

    elif decision == "deny" and confidence >= 0.7:
        log_decision(
            command,
            "deny",
            f"Haiku blocked (confidence: {confidence})",
            "haiku",
            confidence,
        )
        deny(command, f"Haiku blocked (confidence: {confidence:.0%})", rule_id="haiku")

    else:
        # Low confidence or uncertain → let user decide
        ask_user(command, f"Haiku uncertain (confidence: {confidence:.0%})")


if __name__ == "__main__":
    main()

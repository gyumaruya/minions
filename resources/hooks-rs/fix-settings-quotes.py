#!/usr/bin/env python3
"""Fix hook command quotes in Claude settings.json"""

import json
from pathlib import Path


def fix_hook_commands(settings_path):
    """Add quotes around hook commands if missing."""
    with open(settings_path) as f:
        settings = json.load(f)

    if "hooks" not in settings:
        print("No hooks found in settings")
        return

    changes = 0
    for hook_type, hook_list in settings["hooks"].items():
        for hook_config in hook_list:
            for hook in hook_config.get("hooks", []):
                cmd = hook.get("command", "")
                # Check if command needs quotes
                if cmd and not (cmd.startswith('"') and cmd.endswith('"')):
                    hook["command"] = f'"{cmd}"'
                    changes += 1
                    print(f"Fixed: {hook_type} -> {cmd[:50]}...")

    if changes > 0:
        # Backup original
        backup_path = settings_path.parent / f"{settings_path.name}.backup"
        settings_path.rename(backup_path)
        print(f"Backup saved to: {backup_path}")

        # Write fixed settings
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        print(f"\n✓ Fixed {changes} hook commands")
    else:
        print("No changes needed")


if __name__ == "__main__":
    settings_path = Path.home() / ".claude" / "settings.json"
    fix_hook_commands(settings_path)

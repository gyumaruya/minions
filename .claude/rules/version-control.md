# Version Control: jj (Jujutsu)

**Use jj instead of git for all version control operations.**

jj is a Git-compatible VCS with a simpler mental model and better conflict handling.

## Why jj

- Automatic working copy commit (no staging area)
- First-class conflict handling
- Undo any operation
- Git-compatible (works with GitHub, existing git repos)

## Basic Commands

```bash
# Status
jj status
jj log

# Create/modify commits
jj new                    # Create new empty commit
jj commit -m "message"    # Commit with message
jj describe -m "message"  # Change current commit message

# Edit history
jj edit <rev>             # Edit a specific commit
jj squash                 # Squash into parent
jj split                  # Split current commit

# Branches (bookmarks in jj)
jj bookmark list
jj bookmark create <name>
jj bookmark set <name> -r <rev>

# Remote operations
jj git fetch
jj git push
jj git push --bookmark <name>
```

## Workflow

### Daily Work

```bash
# Start working (jj auto-tracks changes)
jj status

# See what changed
jj diff

# Describe your work
jj describe -m "Add feature X"

# Create new commit for next task
jj new
```

### Push to Remote

```bash
# Move bookmark to current commit
jj bookmark set main -r @-

# Push
jj git push
```

### Sync with Remote

```bash
jj git fetch
jj rebase -d main@origin
```

## Key Differences from Git

| Git | jj |
|-----|-----|
| `git add` + `git commit` | `jj commit` (auto-tracks) |
| `git branch` | `jj bookmark` |
| `git checkout` | `jj new <rev>` or `jj edit <rev>` |
| `git stash` | Not needed (use `jj new`) |
| `git rebase -i` | `jj squash`, `jj split`, `jj edit` |

## Important Notes

- **Do NOT use raw git commands** unless necessary for specific git-only features
- Working copy (`@`) is always a commit in progress
- Parent of working copy (`@-`) is usually what you want to push
- Conflicts are first-class: you can commit conflicted files and resolve later

## Common Patterns

### Fix Last Commit

```bash
# Edit parent commit
jj edit @-
# Make changes...
jj squash
jj new
```

### Reorder Commits

```bash
jj rebase -r <commit> -d <destination>
```

### Undo Anything

```bash
jj undo
jj op log    # See operation history
jj op undo <op-id>
```

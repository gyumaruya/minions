---
name: pr-workflow
description: |
  Manage PR lifecycle: review comments, updates, and merge.
  Use when user says "PRをマージ", "レビュー対応", "PR閉じて", "merge PR",
  "resolve comments", or similar PR management requests.
metadata:
  short-description: PR review, update, and merge workflow
disable-model-invocation: false
argument-hint: "[action] [pr-number]"
---

# PR Workflow Skill

Manage the complete PR lifecycle: review responses, updates, and merge.

## Usage

```
/pr-workflow                    # Current PR: show status
/pr-workflow status             # Show PR status and pending reviews
/pr-workflow resolve            # Resolve all addressed review comments
/pr-workflow update             # Update PR description to match changes
/pr-workflow merge              # Merge after all checks pass
/pr-workflow complete           # Full flow: resolve → update → merge
/pr-workflow complete 3         # Specify PR number
```

## Actions

### `status` - Show PR Status

Check the current PR state, review comments, and CI status.

```bash
# Get PR number
PR_NUM=$(gh pr list --state open --json number --jq '.[0].number')

# Show status
gh pr view $PR_NUM --json title,state,reviewDecision,statusCheckRollup

# Show unresolved threads
gh api graphql -f query='
query($pr: Int!) {
  repository(owner: "{owner}", name: "{repo}") {
    pullRequest(number: $pr) {
      reviewThreads(first: 20) {
        nodes { isResolved comments(first:1) { nodes { body } } }
      }
    }
  }
}' -F pr=$PR_NUM
```

### `resolve` - Resolve Review Comments

Resolve all review threads that have been addressed in the code.

**Steps:**
1. Fetch all unresolved review threads via GraphQL
2. For each thread, resolve using `resolveReviewThread` mutation
3. Report resolution status

```bash
# Get thread IDs
THREADS=$(gh api graphql -f query='
query {
  repository(owner: "{owner}", name: "{repo}") {
    pullRequest(number: {pr_num}) {
      reviewThreads(first: 50) {
        nodes { id isResolved }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | .id')

# Resolve each thread
for thread_id in $THREADS; do
  gh api graphql -f query='
    mutation {
      resolveReviewThread(input: {threadId: "'$thread_id'"}) {
        thread { isResolved }
      }
    }
  '
done
```

### `update` - Update PR Description

Update the PR title and body to accurately reflect current changes.

**Steps:**
1. Analyze commits in the PR: `git log main..HEAD`
2. Review changed files: `git diff main --stat`
3. Generate updated summary based on actual changes
4. Update via `gh pr edit`

```bash
# Get current changes
COMMITS=$(git log main..HEAD --oneline)
FILES=$(git diff main --stat)

# Update PR
gh pr edit $PR_NUM --body "$(cat <<'EOF'
## Summary
{generated summary based on commits and changes}

## Changes
{list of key changes}

## Test Plan
{verification steps}

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### `merge` - Merge PR

Merge the PR after verifying all checks pass.

**Pre-merge Checklist:**
1. All CI checks passing
2. No unresolved review threads
3. Branch is up-to-date with base

```bash
# Verify checks
gh pr checks $PR_NUM

# Merge (squash by default)
gh pr merge $PR_NUM --squash --delete-branch
```

### `complete` - Full Workflow

Execute the complete PR finalization workflow:

1. **Resolve** all addressed review comments
2. **Update** PR description if needed
3. **Verify** all checks pass
4. **Merge** the PR
5. **Cleanup** local branches

```bash
# Complete flow
/pr-workflow resolve
/pr-workflow update
gh pr checks $PR_NUM --watch
gh pr merge $PR_NUM --squash --delete-branch

# Sync local
jj git fetch
jj rebase -d main@origin
```

## Dynamic Context

When executing, gather context first:

```bash
# Repository info
REPO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')
OWNER=$(echo $REPO | cut -d'/' -f1)
NAME=$(echo $REPO | cut -d'/' -f2)

# Current PR
PR_NUM=${1:-$(gh pr list --state open --json number --jq '.[0].number')}
```

## Notes

- **Always verify before merge**: Check that review comments are truly addressed
- **Use squash merge**: Keep main branch history clean
- **Delete branch after merge**: Clean up feature branches
- **Sync after merge**: `jj git fetch && jj rebase -d main@origin`

## Language Protocol

- Commands and code: English
- User communication: Japanese
- Report results in Japanese with URLs for easy access

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

### Push to Remote (Feature Branch)

```bash
# Create feature branch and push
jj git push -c @

# Or with explicit bookmark
jj bookmark create feature/xxx -r @
jj git push --bookmark feature/xxx

# Then create PR (draft to avoid auto-review)
gh pr create --draft --title "..." --body "..."
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

- **⛔ Do NOT push directly to main** — Always use Feature Branch → PR → Merge
- **⛔ Always work with an open PR** — Create PR before starting work
- **Auto-push enabled** — When PR is open, push automatically without asking
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

## Auto-Commit on Verification

**動作確認が成功したら自動でコミット・プッシュを行う。**

### Trigger Conditions

以下の場合に自動コミットを提案/実行:

1. **テスト成功時** - `pytest`, `poe test`, `npm test` などが pass
2. **エージェント検証成功時** - `copilot`, `codex`, `gemini` コマンドが正常終了
3. **Lint/Type check 成功時** - `ruff check`, `ty check` が pass

### Auto-Commit Flow

```
変更作成 → 動作確認 → 成功 → 自動コミット提案
                         ↓
              jj describe -m "..." && jj git push -c @ && gh pr create --draft
```

### Quick Ship Command

動作確認後、以下で Feature Branch → PR:

```bash
# Feature branch 作成 & プッシュ & PR 作成（ドラフト）
jj describe -m "..."
jj git push -c @
gh pr create --draft --title "..." --body "..."
```

### Important

- **動作確認なし** → 自動コミットしない
- **テスト失敗** → 自動コミットしない
- **未検証の変更** → 手動確認を要求

## Pull Request Workflow

### PR 作成時のルール

**PR 作成後は必ず URL を表示する:**

```
✅ PR 作成完了: https://github.com/{owner}/{repo}/pull/{number}
```

ユーザーがクリックして PR を開けるようにする。

### Feature Branch → PR → Merge フロー

```bash
# 1. Feature branch 作成
jj bookmark create feature/xxx -r @

# 2. 作業 & コミット
jj describe -m "..."

# 3. プッシュ
jj git push --bookmark feature/xxx

# 4. PR 作成（ドラフト、URL を表示）
gh pr create --draft --title "..." --body "..."
# → https://github.com/.../pull/N

# 5. Ready for review（レビュー準備完了時）
gh pr ready

# 6. マージ後のクリーンアップ
jj git fetch && jj rebase -d main@origin
jj abandon @  # 空のコミットを破棄
```

### Direct to Main

**⛔ 禁止: main への直接プッシュは行わない**

すべての変更は Feature Branch → PR → Merge のフローで行う。

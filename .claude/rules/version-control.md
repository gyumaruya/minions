# Version Control: git

**Use git for all version control operations.**

## ⚠️ CRITICAL RULES

| Rule | Enforcement |
|------|-------------|
| **セッション開始時に自動 PR 作成** | `auto-create-pr.py` フック |
| **PR は必ず draft で作成** | `enforce-draft-pr.py` フック (BLOCK) |
| **PR なしでの編集禁止** | `ensure-pr-open.py` フック (BLOCK) |
| **マージ操作禁止** | `enforce-no-merge.py` フック (BLOCK) |
| **main への直接プッシュ禁止** | Feature Branch → PR → Merge |
| **マージ済みブランチに再プッシュ禁止** | 新規ブランチ・新規 PR を作成 |
| **シークレットのコミット禁止** | `prevent-secrets-commit.py` フック (BLOCK) |

## 自動 PR 作成 & クリーンアップ (Session Start)

セッション開始時に以下が自動実行される:

1. **マージ済みブランチの削除** — 前回セッションのマージ済みブランチをクリーンアップ
2. **main と同期** — `git fetch origin && git checkout main && git pull origin main`
3. オープンな PR があるか確認
4. なければ `feature/session-{hash}` ブランチを作成
5. 自動で draft PR を作成

**フック**: `.claude/hooks/auto-create-pr.py`

## マージ操作の制限

**エージェントによるマージは禁止。** マージはユーザーが行うべき操作。

| 操作 | 許可 |
|------|------|
| `gh pr ready` | ✅ OK |
| `gh pr view` | ✅ OK |
| `gh pr merge` | ⛔ BLOCK |

マージはユーザーが GitHub UI または CLI で実行してください。

## シークレット検出

以下のパターンを検出してコミットをブロック:

- AWS Access Key / Secret Key
- OpenAI / Anthropic API Key
- GitHub Token
- Google API Key
- Slack Token
- Private Keys (PEM)
- Generic secrets (api_key, password)
- Database URLs
- JWT Tokens

**フック**: `.claude/hooks/prevent-secrets-commit.py`

## Basic Commands

```bash
# Status
git status

# See history
git log --oneline --graph --all

# Create commits
git add <files>
git commit -m "message"

# Branches
git branch                    # List branches
git checkout -b <name>        # Create and switch to new branch
git checkout <name>           # Switch to branch
git branch -d <name>          # Delete branch

# Remote operations
git fetch origin
git pull origin <branch>
git push origin <branch>
git push -u origin <branch>   # Push and set upstream
```

## Workflow

### Daily Work

```bash
# Check status
git status

# See what changed
git diff

# Stage changes
git add <files>

# Commit
git commit -m "メッセージ

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Push
git push
```

### Push to Remote (Feature Branch)

```bash
# Create feature branch and push
git checkout -b feature/xxx
git push -u origin feature/xxx

# Then create PR (draft to avoid auto-review)
gh pr create --draft --title "..." --body "..."
```

### Sync with Remote

```bash
git fetch origin
git checkout main
git pull origin main
git checkout <feature-branch>
git rebase main
```

## Key Differences from jj

| jj | git |
|-----|-----|
| `jj status` | `git status` |
| `jj log` | `git log --oneline --graph` |
| `jj describe -m "msg"` | `git commit -m "msg"` |
| `jj new` | `git checkout -b <branch>` |
| `jj bookmark create` | `git checkout -b <branch>` |
| `jj git push -c @` | `git push -u origin <branch>` |
| `jj git fetch` | `git fetch origin` |
| `jj rebase -d main@origin` | `git rebase origin/main` |

## Important Notes

- **⛔ Do NOT push directly to main** — Always use Feature Branch → PR → Merge
- **⛔ Always work with an open PR** — Create PR before starting work
- **Auto-push enabled** — When PR is open, push automatically without asking
- **Secrets are blocked** — Automatic detection prevents committing API keys
- Use feature branches for all changes
- Always include Co-Authored-By in commit messages

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
              git add -A && git commit -m "..." && git push
```

### Quick Ship Command

動作確認後、以下で Feature Branch → PR:

```bash
# Commit & push & PR 作成（ドラフト）
git add -A
git commit -m "機能追加

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push -u origin <branch-name>
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
git checkout -b feature/xxx

# 2. 作業 & コミット
git add <files>
git commit -m "変更内容

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# 3. プッシュ
git push -u origin feature/xxx

# 4. PR 作成（ドラフト、URL を表示）
gh pr create --draft --title "..." --body "..."
# → https://github.com/.../pull/N

# 5. Ready for review（レビュー準備完了時）
gh pr ready

# 6. マージ後のクリーンアップ
git checkout main
git pull origin main
git branch -d feature/xxx
```

### Direct to Main

**⛔ 禁止: main への直接プッシュは行わない**

すべての変更は Feature Branch → PR → Merge のフローで行う。

## Common Patterns

### Amend Last Commit

```bash
# Modify last commit
git add <files>
git commit --amend --no-edit

# Or change message
git commit --amend -m "新しいメッセージ"
```

### Undo Changes

```bash
# Unstage files
git reset HEAD <file>

# Discard working directory changes
git checkout -- <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1
```

### Rebase

```bash
# Rebase on main
git fetch origin
git rebase origin/main

# Interactive rebase (last 3 commits)
git rebase -i HEAD~3
```

## Commit Message Format

**必須: 日本語で記述**

```
短い要約（50文字以内）

詳細な説明（必要に応じて）
- 変更内容
- 理由
- 影響範囲

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### 良い例

```
ユーザー認証機能を追加

- JWT トークンベースの認証を実装
- ログイン/ログアウトエンドポイントを追加
- セッション管理を Redis で実装

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### 悪い例

```
Add user authentication   # ❌ 英語
update                    # ❌ 詳細不足
fix bug                   # ❌ 何のバグ？
```

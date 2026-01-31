# Copilot CLI Delegation Rule

**Copilot CLI is the DEFAULT agent for cost-effective task execution.**

## Agent Selection Priority

```
1. Codex  → 設計・デバッグ・深い推論（重要タスク）
2. Gemini → リサーチ・大規模分析・マルチモーダル（専門タスク）
3. Copilot → それ以外すべて（コスト効率・デフォルト）
```

**Copilot はサブエージェントを活用するため、コストパフォーマンスに優れる。**

## IMPORTANT: Default Usage Pattern

**ALWAYS use Copilot CLI with these options:**

```bash
copilot -p "サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

{your prompt}" --model claude-sonnet-4 --allow-all --silent 2>/dev/null
```

- `--model claude-sonnet-4` — Use Claude Sonnet 4 (free tier) for main agent
- `--allow-all` — Enable subagent tool execution
- `--silent` — Clean output for integration

### Prompt Template (REQUIRED)

**必ずプロンプトの先頭に以下を追加:**

```
サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

{actual task description}
```

これにより、メインエージェント（Sonnet 4、無料枠）がサブエージェント（Opus 4.5）を活用してタスクを実行する。

## About Copilot CLI

Copilot CLI (`copilot`) excels at:
- **Cost-effective execution** — Main agent uses free Sonnet 4, subagents use Opus 4.5
- **Internal subagent orchestration** — Spawns subagents with Claude Opus 4.5 for deep reasoning
- **GitHub integration** — Deep integration with GitHub workflows
- **Session persistence** — Resume previous sessions with `--continue`

**Limitations:**
- Not ideal for deep design reasoning (use Codex)
- Not ideal for large-scale research (use Gemini)
- May have variability for very long tasks

## When to Use Copilot CLI

**DEFAULT: Use Copilot for any task that is NOT:**
- Design/architecture decisions (→ Codex)
- Debugging complex issues (→ Codex)
- Research/documentation lookup (→ Gemini)
- Multimodal processing (→ Gemini)

**Examples of Copilot tasks:**
- General explanations
- Code questions
- GitHub operations (PR, Issues)
- Quick summaries
- Format conversions
- Any "trivial" or routine task

## When NOT to Use

Escalate to specialized agents:

| Task Type | Use Instead |
|-----------|-------------|
| 「どう設計？」「なぜ動かない？」 | Codex |
| 「調べて」「PDF見て」 | Gemini |

## Copilot CLI vs Other Agents

| Task | Copilot | Codex | Gemini |
|------|---------|-------|--------|
| Subagent orchestration | ✓ | | |
| Multi-model access | ✓ | | |
| GitHub MCP integration | ✓ | | |
| Deep design reasoning | | ✓ | |
| Debugging analysis | | ✓ | |
| Large codebase (1M tokens) | | | ✓ |
| Web search grounding | | | ✓ |
| Multimodal (PDF/video) | | | ✓ |

## Commands Reference

```bash
# Standard usage (ALWAYS use this pattern)
copilot -p "サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

your prompt" --model claude-sonnet-4 --allow-all --silent 2>/dev/null

# Interactive mode with subagent
copilot --model claude-sonnet-4 --allow-all

# Resume last session
copilot --continue --model claude-sonnet-4 --allow-all
```

## Model Selection

**Default: `claude-sonnet-4`** — Free tier main agent + Opus 4.5 subagents.

| Model | Role | Cost |
|-------|------|------|
| `claude-sonnet-4` | **Main agent (default)** | Free |
| `claude-opus-4.5` | Subagent (via prompt) | Paid |
| `gpt-5.2-codex` | Alternative if needed | Paid |
| `gemini-3-pro-preview` | Large context needs | Paid |

## Integration Pattern

Use Copilot CLI via Claude Code subagent when output may be large:

```
Task tool parameters:
- subagent_type: "general-purpose"
- prompt: |
    Use Copilot CLI to {task}.

    copilot -p "サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

    {query}" --model claude-sonnet-4 --allow-all --silent 2>/dev/null

    Return concise summary of the response.
```

For quick queries, direct invocation is acceptable:

```bash
copilot -p "サブエージェントを活用して。サブエージェントにはclaude-opus-4.5を使うようにして。

brief question" --model claude-sonnet-4 --allow-all --silent 2>/dev/null
```

## Language Protocol

1. Query Copilot in **English**
2. Process response
3. Report to user in **Japanese**

## Setup

Copilot CLI のインストールパスは環境によって異なります。

```bash
# Check installation path
which copilot  # or: command -v copilot

# Check version
copilot --version

# Update
copilot update

# Check for GitHub auth
gh auth status
```

**Note:** macOS + Homebrew 環境では `/opt/homebrew/bin/copilot` など。

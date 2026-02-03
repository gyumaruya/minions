# グローバル設定とプロジェクト設定の設計

minions プロジェクトを「ベース」として他のプロジェクトでも活用するための設計ドキュメント。

---

## 実装状況（2026-02-04）

### 完了した作業

#### 1. グローバル記憶の実装

**記憶パスの変更:**
```
変更前: <project>/.claude/memory/events.jsonl
変更後: ~/.config/ai/memory/events.jsonl
```

**パス解決の優先順位:**
1. `AI_MEMORY_PATH` 環境変数（設定時）
2. `~/.config/ai/memory/events.jsonl`（デフォルト）

**影響を受けたフック:**
- `load-memories` - 記憶読み込み
- `auto-learn` - 自動学習
- `pre-tool-recall` - ツール実行前の記憶参照
- `post-tool-record` - ツール実行結果の記録

すべて `MemoryStorage::default_path()` を使用するよう修正。

#### 2. グローバルフックの実装

**構成:**
```
~/.config/ai/
├── hooks/
│   └── bin/ → ~/minions/hooks-rs/target/release/ (symlink)
└── memory/
    └── events.jsonl (217 events, minions から移行)

~/.claude/settings.json
├── 全 23 フック定義
├── permissions（セキュリティポリシー）
└── enabledPlugins

minions/.claude/settings.json
└── env のみ（最小限）
```

**グローバル化されたフック（23個）:**

| カテゴリ | フック | タイミング |
|---------|--------|-----------|
| **記憶** | load-memories, auto-learn, pre-tool-recall, post-tool-record | UserPromptSubmit, PreToolUse, PostToolUse |
| **セキュリティ** | prevent-secrets-commit, ensure-noreply-email, enforce-japanese | PreToolUse:Bash |
| **PR ワークフロー** | auto-create-pr, enforce-draft-pr, enforce-no-merge, ensure-pr-open | UserPromptSubmit, PreToolUse |
| **階層・委譲** | enforce-hierarchy, enforce-delegation, hierarchy-permissions | PreToolUse, PostToolUse |
| **提案** | check-codex-before-write, check-codex-after-plan, suggest-gemini-research, post-implementation-review | PreToolUse, PostToolUse |
| **開発フロー** | lint-on-save, post-test-analysis, auto-commit-on-verify | PostToolUse |
| **ルーティング** | agent-router, log-cli-tools | UserPromptSubmit, PostToolUse:Bash |

#### 3. セットアップスクリプト

**場所:** `~/minions/scripts/setup-global-config.sh`

**実行内容:**
1. `~/.config/ai/` ディレクトリ構造作成
2. フックバイナリへの symlink 作成
3. minions の記憶をグローバルに移行
4. `~/.claude/settings.json` にグローバルフック設定
5. `minions/.claude/settings.json` を最小化

**使い方:**
```bash
cd ~/minions/hooks-rs && cargo build --release
~/minions/scripts/setup-global-config.sh
```

---

## 今後の方針

### Phase 1: グローバル記憶の運用（現在）

**状態:** ✅ 完了

- すべての記憶が `~/.config/ai/memory/events.jsonl` に統合
- グローバル/ローカル判断ロジックは未実装（すべてグローバル）
- 全プロジェクトで共通の記憶を使用

**利点:**
- 一度学習した好みが全プロジェクトに適用
- セットアップ済みなら新プロジェクトでも即座に動作

**制限:**
- プロジェクト固有の記憶が混在（現状は許容）

### Phase 2: ローカル記憶の追加（次のステップ）

**目的:** プロジェクト固有の記憶とグローバル記憶を分離

**実装予定:**
```
~/.config/ai/memory/events.jsonl           # グローバル（好み、ワークフロー）
<project>/.claude/memory/events.jsonl     # ローカル（プロジェクト固有）
```

**振り分けロジック（検討中）:**

| 記憶タイプ | 保存先 | 例 |
|-----------|--------|-----|
| 好み (`preference`) | グローバル | 「PRは日本語で書く」 |
| ワークフロー (`workflow`) | グローバル | 「コミット後は自動でPR作成」 |
| プロジェクト固有エラー | ローカル | 「このAPIのタイムアウトは30秒」 |
| プロジェクト固有決定 | ローカル | 「認証にJWTを使用」 |

**実装方法（案）:**
1. 環境変数で判断: `AI_MEMORY_SCOPE=global|local`
2. LLM判断: フック内でコンテンツを分析
3. ユーザー確認: 記憶時に確認プロンプト

### Phase 3: Tool Adapter層（長期）

**Codex の未来志向レビューより:**

```
~/.config/ai/
├── tools/
│   ├── claude/
│   ├── copilot/
│   ├── codex/
│   └── gemini/
└── compat/              # バージョン互換マッピング
```

**目的:**
- ツール進化時の破綻を防ぐ
- 新旧ツールバージョン間の差分を吸収

**実装は必要になってから:**
- 現状は Phase 1 で十分
- ツールのAPI変更が頻繁になったら検討

---

## 新プロジェクトでのセットアップ

### 前提

- minions プロジェクトで `setup-global-config.sh` 実行済み
- グローバルフック・記憶が設定済み

### 新プロジェクトで必要な作業

**なし。** グローバル設定が自動適用される。

### オプション: プロジェクト固有設定

プロジェクト固有の設定が必要な場合のみ:

```bash
mkdir -p <project>/.claude
cat > <project>/.claude/settings.json << 'EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "PROJECT_SPECIFIC_VAR": "value"
  }
}
EOF
```

**Note:** フックはグローバルから継承されるため、プロジェクトごとの設定は不要。

---

## トラブルシューティング

### 記憶が読み込まれない

**確認:**
```bash
# グローバル記憶の存在確認
ls -la ~/.config/ai/memory/events.jsonl

# 記憶の内容確認
head -5 ~/.config/ai/memory/events.jsonl
```

**解決:**
```bash
# セットアップスクリプトを再実行
~/minions/scripts/setup-global-config.sh
```

### フックが動作しない

**確認:**
```bash
# フックバイナリの存在確認
ls ~/.config/ai/hooks/bin/

# symlink の確認
readlink ~/.config/ai/hooks/bin
# -> /Users/takuya/minions/hooks-rs/target/release

# グローバル設定の確認
grep "hooks" ~/.claude/settings.json
```

**解決:**
```bash
# フックをリビルド
cd ~/minions/hooks-rs && cargo build --release

# symlink を再作成
rm ~/.config/ai/hooks/bin
ln -sf ~/minions/hooks-rs/target/release ~/.config/ai/hooks/bin
```

### 環境変数でパスをオーバーライド

特定のプロジェクトで異なる記憶を使いたい場合:

```bash
# プロジェクト固有の記憶を使用
export AI_MEMORY_PATH="/path/to/project/.claude/memory/events.jsonl"
```

`.claude/settings.json` の `env` セクションに追加も可能:
```json
{
  "env": {
    "AI_MEMORY_PATH": "/path/to/custom/memory.jsonl"
  }
}
```

---

## 設計判断の記録

### なぜ `~/.config/ai/` か

**理由:**
- XDG Base Directory Specification 準拠
- Claude Code 固有（`~/.claude/`）ではなく、ツール非依存
- 将来的に他のAIツールとも共有可能

### なぜ manifest.json を削除したか

**3つの視点からの合意:**
- 実用主義者: 「git で十分」
- 未来志向: 「配布時に必要になってから」
- ミニマリスト: 「不要」

現状は git でバージョン管理。必要になったら追加。

### なぜすべてのフックをグローバルにしたか

**ユーザー要望:** 「minionsのフックは基本グローバルオンリーになるイメージ」

**利点:**
- 新プロジェクトで即座に使える
- 一貫したガードレールが適用される
- セットアップが簡単

**プロジェクト固有の動作:**
- `auto-create-pr` などは `CLAUDE_PROJECT_DIR` を参照
- プロジェクトごとに異なるリポジトリでPRを作成
- グローバルでも問題なく動作

---

## 現状の仕組み（Claude Code の仕様）

### 設定ファイルの階層

Claude Code は 5 段階の優先順位システムを採用：

```
優先度: 高い ← ────────────────────────────── → 低い

1. Managed settings     (IT管理者配置、オーバーライド不可)
2. Command line args    (セッション内でのみ有効)
3. Local project        (.claude/settings.local.json)
4. Shared project       (.claude/settings.json)
5. User settings        (~/.claude/settings.json)
```

### 設定スコープの詳細

| スコープ | 場所 | 対象 | Git共有 | ユースケース |
|---------|------|------|---------|------------|
| **Managed** | `/Library/Application Support/ClaudeCode/` | 全ユーザー | - | セキュリティポリシー |
| **User** | `~/.claude/` | 全プロジェクト | ✗ | 個人設定、グローバルガードレール |
| **Project** | `.claude/` | リポジトリ共有者 | ✓ | チーム共有設定 |
| **Local** | `.claude/*.local.*` | 自分のみ | ✗ | プロジェクト固有の個人設定 |

---

## 実行順序とマージ動作

### フック（Hooks）: 加算的実行

**両方のフックが実行される**（オーバーライドではない）

```
~/.claude/settings.json のフック
        ＋
.claude/settings.json のフック
        ＋
.claude/settings.local.json のフック
        ↓
    すべて並列実行される
```

**重要な動作:**
- 同一イベントのフックは**並列実行**（順序保証なし）
- どちらかが `exit 2` を返すと**ツール実行がブロック**
- 同一ハンドラーは自動削除（重複実行防止）

**例:**
```
グローバル: prevent-secrets-commit
プロジェクト: lint-on-save
    ↓
両方実行される
```

### メモリ（CLAUDE.md）: 階層的ロード

**すべてのメモリがコンテキストに注入される**

```
~/.claude/CLAUDE.md (グローバル)
        ↓ ロード
.claude/CLAUDE.md (プロジェクト)
        ↓ ロード
CLAUDE.local.md (個人)
        ↓
    すべてコンテキストに注入
```

**インポート構文:**
```markdown
# Main Instructions
@docs/git-instructions.md
@README
```
- 最大深度: 5 ホップ
- 循環参照は安全に処理

### 設定（permissions 等）: オーバーライド

**より具体的なスコープが優先**

```
User < Project < Local の優先順位
より restrictive な設定が勝つ（deny > allow）
```

| グローバル | プロジェクト | 結果 |
|-----------|-------------|------|
| `Bash(*)` 許可 | `Bash(rm -rf)` 拒否 | **拒否が勝つ** |
| `Edit(*)` 許可 | 設定なし | **許可** |

---

## 現在の環境状態

### グローバル（~/.claude/）

```
~/.claude/
├── settings.json          # プラグインのみ（フックなし）
├── CLAUDE.md              # 存在しない
├── history.jsonl          # コマンド履歴
├── projects/              # プロジェクト登録
├── session-env/           # セッション環境
└── plugins/               # インストール済みプラグイン
```

**現状**: グローバル設定はほぼ空。

### プロジェクト（~/minions/.claude/）

```
~/minions/.claude/
├── settings.json          # 23個のRustフック定義
├── settings.local.json    # ローカルオーバーライド
├── config.json            # エージェント設定
├── memory/                # 記憶システム
│   ├── events.jsonl       # イベントログ
│   └── sessions/          # セッション別ログ
├── rules/                 # コーディングルール（10ファイル）
├── agents/                # エージェント指示書
├── docs/                  # ドキュメント
└── hooks/                 # レガシーPythonフック（Rustに移行済み）
```

**現状**: すべての設定が minions プロジェクト内に閉じている。

---

## 提案: グローバル設定のセットアップ

### 目標

minions の「ガードレール」を全プロジェクトに適用しつつ、各プロジェクト固有の設定も追加できるようにする。

### 提案構成

```
~/.claude/
├── settings.json          # グローバルフック（ガードレール）
├── CLAUDE.md              # グローバルルール・好み
└── hooks/                 # 共通フックバイナリ
    └── → ~/minions/hooks-rs/target/release/ (シンボリックリンク)

各プロジェクト/.claude/
├── settings.json          # プロジェクト固有フック（追加）
├── CLAUDE.md              # プロジェクト固有ルール
└── memory/                # プロジェクト固有の記憶
```

### グローバルに配置すべきもの

| コンポーネント | 理由 |
|--------------|------|
| **prevent-secrets-commit** | 全プロジェクトでシークレット漏洩防止 |
| **enforce-japanese** | PR/コミットを日本語で（個人の好み） |
| **load-memories** | グローバル記憶のロード |
| **基本ルール** | 言語設定、コーディング原則 |

### プロジェクト固有に残すべきもの

| コンポーネント | 理由 |
|--------------|------|
| **auto-create-pr** | プロジェクトごとにリポジトリが異なる |
| **lint-on-save** | プロジェクトごとにリンターが異なる |
| **enforce-hierarchy** | minions 固有のエージェント階層 |
| **プロジェクト固有メモリ** | プロジェクト固有の学習 |

---

## 実装ステップ

### Step 1: グローバル設定ディレクトリ準備

```bash
# グローバルフック用ディレクトリ
mkdir -p ~/.claude/hooks

# minions のフックバイナリへシンボリックリンク
ln -s ~/minions/hooks-rs/target/release ~/.claude/hooks/bin
```

### Step 2: グローバル settings.json 作成

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/bin/prevent-secrets-commit",
            "timeout": 5000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/bin/load-memories",
            "timeout": 5000
          }
        ]
      }
    ]
  },
  "permissions": {
    "deny": [
      "Edit(~/.ssh/*)",
      "Edit(~/.aws/*)",
      "Read(**/.env)",
      "Bash(rm -rf /)"
    ]
  }
}
```

### Step 3: グローバル CLAUDE.md 作成

```markdown
# Global Instructions

## Language Protocol
- 思考・コード: 英語
- ユーザー対話: 日本語
- PR/コミット: 日本語

## Security
- シークレットをコミットしない
- .env ファイルを読まない

## Preferences
- PRは日本語で書く
- コミット後は自動でPR作成を提案
```

### Step 4: 新プロジェクト用テンプレート

```bash
# 新プロジェクトのセットアップ
mkdir -p new-project/.claude
cat > new-project/.claude/settings.json << 'EOF'
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Project-specific hook'"
          }
        ]
      }
    ]
  }
}
EOF
```

---

## 結果

```
グローバルフック (prevent-secrets-commit, load-memories)
        ＋
プロジェクトフック (lint-on-save, auto-create-pr)
        ↓
    すべて実行される

グローバルメモリ (日本語で話す、基本ルール)
        ＋
プロジェクトメモリ (このプロジェクトはRust、特定のワークフロー)
        ↓
    すべてコンテキストに注入
```

---

## 注意事項

1. **フックの競合**: 同じツールに対して矛盾するフックがあると両方実行される
2. **パスの解決**: グローバルフックでは絶対パスまたは `~` を使用
3. **環境変数**: `$CLAUDE_PROJECT_DIR` はプロジェクト固有のため、グローバルでは使用不可
4. **デバッグ**: `/hooks` コマンドで現在のフック設定を確認可能

---

## 関連ドキュメント

- [Claude Code 公式ドキュメント](https://docs.anthropic.com/en/docs/claude-code)
- `.claude/rules/` - コーディングルール
- `.claude/docs/MEMORY_SYSTEM.md` - 記憶システム

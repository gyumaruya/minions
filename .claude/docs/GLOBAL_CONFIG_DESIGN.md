# グローバル設定とプロジェクト設定の設計

minions プロジェクトを「ベース」として他のプロジェクトでも活用するための設計ドキュメント。

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

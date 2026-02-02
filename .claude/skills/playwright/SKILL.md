---
name: playwright
description: Playwrightを使用してWebページのスクリーンショットを取得
metadata:
  short-description: ブラウザ自動化・スクリーンショット取得
argument-hint: "/playwright screenshot <url> [--output <path>]"
---

# Playwright — ブラウザ自動化スキル

Playwrightを使用してWebページのスクリーンショットを取得するスキル。

## 使い方

```bash
# 基本（スクリーンショット取得）
/playwright screenshot <url>

# 出力先指定
/playwright screenshot <url> --output ./screenshot.png

# フルページ
/playwright screenshot <url> --full-page

# ビューポート指定
/playwright screenshot <url> --width 1920 --height 1080

# 待機時間指定
/playwright screenshot <url> --wait 5
```

## 実行方法

このスキルは以下のPythonスクリプトを実行します:

```bash
uv run python .claude/skills/playwright/screenshot.py <url> [options]
```

## オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--output`, `-o` | 出力ファイルパス | `./screenshot.png` |
| `--full-page` | フルページスクリーンショット | `False` |
| `--width` | ビューポート幅 | `1280` |
| `--height` | ビューポート高さ | `800` |
| `--wait` | 読み込み待機秒数 | `2` |

## 前提条件

```bash
# 依存関係インストール
uv add --dev playwright
uv run playwright install chromium
```

## 例

```bash
# GitHubのREADMEをスクリーンショット
/playwright screenshot https://github.com/user/repo --full-page

# ローカルファイルのプレビュー
/playwright screenshot file:///path/to/file.html --output preview.png

# 高解像度スクリーンショット
/playwright screenshot https://example.com --width 1920 --height 1080 --output hd.png

# 読み込み待機を増やす
/playwright screenshot https://slow-loading-site.com --wait 5
```

## 技術詳細

- **ブラウザ**: Chromium (headless mode)
- **待機戦略**: networkidle状態まで待機 + 追加待機時間
- **出力形式**: PNG (デフォルト)
- **ビューポート**: カスタマイズ可能

## トラブルシューティング

### Chromiumがインストールされていない

```bash
uv run playwright install chromium
```

### スクリーンショットが真っ白

`--wait` オプションで待機時間を増やしてください:

```bash
/playwright screenshot <url> --wait 5
```

### フルページが長すぎる

ビューポートの高さを調整してください:

```bash
/playwright screenshot <url> --full-page --height 2000
```

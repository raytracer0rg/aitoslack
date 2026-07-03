name: Fetch RSS Feeds

on:
  schedule:
    # 例: 毎日 21:00 UTC (JST 06:00) に実行。Routine実行時刻の前になるよう調整してください。
    - cron: "0 21 * * *"
  workflow_dispatch: {}  # 手動実行用ボタンも有効化しておく

permissions:
  contents: write  # feeds.json をコミットするために必要

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

      - name: Python セットアップ
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 依存パッケージインストール
        run: pip install -r requirements.txt

      - name: フィード取得スクリプト実行
        run: python scripts/fetch_feeds.py

      - name: feeds.json をコミット・プッシュ
        run: |
          git config user.name "feed-relay-bot"
          git config user.email "actions@users.noreply.github.com"
          git add feeds.json
          if git diff --cached --quiet; then
            echo "変更なし。コミットをスキップします。"
          else
            git commit -m "chore: update feeds.json ($(date -u +'%Y-%m-%dT%H:%M:%SZ'))"
            git pull --rebase origin main
            git push
          fi

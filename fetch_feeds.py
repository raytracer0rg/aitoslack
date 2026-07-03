#!/usr/bin/env python3
"""
GitHub Actionsのランナー(egress制限なし)からRSSフィードを取得し、
記事一覧(タイトル・URL・公開日・取得元)をJSONにまとめて出力する。

Claude Code Routines側は、このスクリプトが生成した feeds.json を
raw.githubusercontent.com 経由で取得するだけで済むようにする。
これにより、Routines実行環境のegressポリシーによる403問題を回避する。

使い方:
  python scripts/fetch_feeds.py

出力:
  feeds.json (リポジトリ直下)
"""

import json
import hashlib
from datetime import datetime, timezone
from time import mktime

import feedparser

# ============================================================
# ここに実際に使うフィードを列挙する。
# 既存の AI自動化ナビ で使っている SOURCE_FEEDS の内容をそのまま移植してください。
# (Google News RSS の検索クエリ、はてブRSS、Techmeme等)
# ============================================================
FEEDS = [
    # 例: Google News RSS (検索クエリベース、日本語)
    {
        "name": "Google News - Claude Code Routines",
        "url": "https://news.google.com/rss/search?q=Claude+Code+Routines&hl=ja&gl=JP&ceid=JP:ja",
    },
    {
        "name": "Google News - loop engineering",
        "url": "https://news.google.com/rss/search?q=%22loop+engineering%22+AI&hl=en-US&gl=US&ceid=US:en",
    },
    # 例: はてなブックマーク RSS
    {
        "name": "はてなブックマーク - テクノロジー",
        "url": "https://b.hatena.ne.jp/hotentry/it.rss",
    },
    # 例: Techmeme
    {
        "name": "Techmeme",
        "url": "https://www.techmeme.com/feed.xml",
    },
    # 必要に応じて追加
    # {"name": "Anthropic Blog", "url": "https://www.anthropic.com/rss.xml"},
    # {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml"},
]

# 何時間以内の記事を候補として残すか
FRESHNESS_HOURS = 72


def parse_entry_datetime(entry):
    """feedparserのエントリから公開日時(UTC)を取り出す。取れなければNone。"""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None


def make_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def main():
    now = datetime.now(timezone.utc)
    items = {}
    fetch_errors = []

    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                fetch_errors.append({"source": feed["name"], "url": feed["url"], "error": str(parsed.bozo_exception)})
                continue
        except Exception as e:
            fetch_errors.append({"source": feed["name"], "url": feed["url"], "error": str(e)})
            continue

        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue

            published_at = parse_entry_datetime(entry)
            age_hours = None
            if published_at:
                age_hours = round((now - published_at).total_seconds() / 3600, 1)

            # 鮮度フィルタ: 公開日が取れて、かつ古すぎる場合はスキップ
            if published_at and age_hours is not None and age_hours > FRESHNESS_HOURS:
                continue

            item_id = make_id(link)
            # 同じ記事が複数フィードに出た場合はソースを追記して重複除去
            if item_id in items:
                if feed["name"] not in items[item_id]["sources"]:
                    items[item_id]["sources"].append(feed["name"])
                continue

            items[item_id] = {
                "id": item_id,
                "title": title.strip(),
                "url": link,
                "published_at": published_at.isoformat() if published_at else None,
                "published_at_confirmed": published_at is not None,
                "age_hours": age_hours,
                "sources": [feed["name"]],
            }

    result = {
        "generated_at": now.isoformat(),
        "freshness_window_hours": FRESHNESS_HOURS,
        "item_count": len(items),
        "items": sorted(
            items.values(),
            key=lambda x: (x["age_hours"] is None, x["age_hours"] or 0),
        ),
        "fetch_errors": fetch_errors,
    }

    with open("feeds.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"取得記事数: {len(items)} / 取得失敗フィード数: {len(fetch_errors)}")


if __name__ == "__main__":
    main()

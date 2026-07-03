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
# AI自動化ナビ の Routines プロンプトから移植したフィード一覧。
# 各フィードに region / freshness_hours を持たせ、フィードごとに
# 鮮度ウィンドウ(3日 or 7日)を変えられるようにしてある。
#
# 注記:
# - Hugging Face Papers (https://huggingface.co/papers) はRSSではなく
#   通常のHTMLページのため、feedparserでは取得できない。別途対応が必要。
# - 「公式の一次ソース」(Claude Code changelog, Anthropic Newsroom,
#   ChatGPT release notes, Gemini changelog) はRSS提供がないため、
#   ここには含めない。従来通りRoutine側でのWeb検索/直接確認に任せる。
# - 「Web検索で必ず補う」セクションもRSS化できないため、
#   Routine側のプロンプトにこれまで通り残しておくこと。
# ============================================================
FEEDS = [
    # ---------------- 海外 ----------------
    {
        "name": "Google News (EN) - AI agent automation",
        "url": "https://news.google.com/rss/search?q=AI+agent+automation+when:3d&hl=en-US&gl=US&ceid=US:en",
        "region": "overseas",
        "freshness_hours": 72,
    },
    {
        "name": "Google News (EN) - Claude/ChatGPT automation",
        "url": "https://news.google.com/rss/search?q=Claude+Code+OR+ChatGPT+automation+when:3d&hl=en-US&gl=US&ceid=US:en",
        "region": "overseas",
        "freshness_hours": 72,
    },
    {
        "name": "Google News (EN) - loop engineering",
        "url": "https://news.google.com/rss/search?q=loop+engineering+AI+agent+when:7d&hl=en-US&gl=US&ceid=US:en",
        "region": "overseas",
        "freshness_hours": 168,
    },
    {
        "name": "Techmeme",
        "url": "https://www.techmeme.com/feed.xml",
        "region": "overseas",
        "freshness_hours": 72,
    },
    {
        "name": "Hacker News - AI agent",
        "url": "https://hnrss.org/newest?q=AI+agent&points=30",
        "region": "overseas",
        "freshness_hours": 72,
    },
    {
        "name": "Reddit - AI_Agents/automation/ClaudeAI top",
        "url": "https://www.reddit.com/r/AI_Agents+automation+ClaudeAI/top/.rss?sort=top&t=day",
        "region": "overseas",
        "freshness_hours": 72,
    },
    # ---------------- 日本 ----------------
    {
        "name": "はてブ - AIエージェント",
        "url": "https://b.hatena.ne.jp/search/text?q=AI%E3%82%A8%E3%83%BC%E3%82%B8%E3%82%A7%E3%83%B3%E3%83%88&mode=rss&sort=recent&users=5",
        "region": "japan",
        "freshness_hours": 72,
    },
    {
        "name": "はてブ - AI 自動化",
        "url": "https://b.hatena.ne.jp/search/text?q=AI+%E8%87%AA%E5%8B%95%E5%8C%96&mode=rss&sort=recent&users=5",
        "region": "japan",
        "freshness_hours": 72,
    },
    {
        "name": "はてブ - ループエンジニアリング",
        "url": "https://b.hatena.ne.jp/search/text?q=%E3%83%AB%E3%83%BC%E3%83%97%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%AA%E3%83%B3%E3%82%B0&mode=rss&sort=recent&users=3",
        "region": "japan",
        "freshness_hours": 168,
    },
    {
        "name": "Google News (JA) - AI 自動化",
        "url": "https://news.google.com/rss/search?q=AI+%E8%87%AA%E5%8B%95%E5%8C%96+when:3d&hl=ja&gl=JP&ceid=JP:ja",
        "region": "japan",
        "freshness_hours": 72,
    },
    {
        "name": "Google News (JA) - Claude/ChatGPT 自動化",
        "url": "https://news.google.com/rss/search?q=Claude+OR+ChatGPT+%E8%87%AA%E5%8B%95%E5%8C%96+when:3d&hl=ja&gl=JP&ceid=JP:ja",
        "region": "japan",
        "freshness_hours": 72,
    },
    {
        "name": "Impress Watch",
        "url": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",
        "region": "japan",
        "freshness_hours": 72,
    },
]

# 個別のfreshness_hoursが指定されていない場合のデフォルト
DEFAULT_FRESHNESS_HOURS = 72


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
        freshness_hours = feed.get("freshness_hours", DEFAULT_FRESHNESS_HOURS)
        try:
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                fetch_errors.append({"source": feed["name"], "url": feed["url"], "error": str(parsed.bozo_exception)})
                continue
        except Exception as e:
            fetch_errors.append({"source": feed["name"], "url": feed["url"], "error": str(e)})
            continue

        if not parsed.entries:
            # entries が空(取得はできたが0件、または構造的に落ちている)ケースも記録しておく
            fetch_errors.append({"source": feed["name"], "url": feed["url"], "error": "0 entries returned"})

        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue

            published_at = parse_entry_datetime(entry)
            age_hours = None
            if published_at:
                age_hours = round((now - published_at).total_seconds() / 3600, 1)

            # 鮮度フィルタ: 公開日が取れて、かつフィード個別の鮮度ウィンドウより古い場合はスキップ
            if published_at and age_hours is not None and age_hours > freshness_hours:
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
                "region": feed.get("region"),
                "sources": [feed["name"]],
            }

    region_counts = {}
    for item in items.values():
        r = item.get("region") or "unknown"
        region_counts[r] = region_counts.get(r, 0) + 1

    result = {
        "generated_at": now.isoformat(),
        "default_freshness_window_hours": DEFAULT_FRESHNESS_HOURS,
        "item_count": len(items),
        "region_counts": region_counts,
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

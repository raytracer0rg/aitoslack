#!/usr/bin/env python3
# feeds.json から既出URLを除外し、posted_history.json を更新する（決定論的）
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FEEDS_PATH = Path("feeds.json")
HISTORY_PATH = Path("posted_history.json")
RETENTION_DAYS = 14          # この日数を過ぎたURLは再登場を許可
URL_KEY = "url"              # ★feeds.jsonの各itemでURLが入っているキー名（要確認。"link"かも）

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default

def main():
    now = datetime.now(timezone.utc)
    history = load_json(HISTORY_PATH, {"posted": []})
    posted = history.get("posted", [])
    seen = {e["url"] for e in posted if "url" in e}

    feeds = load_json(FEEDS_PATH, [])
    if isinstance(feeds, dict):          # {"items":[...]} 形式にも対応
        items, container = feeds.get("items", []), "dict"
    else:
        items, container = feeds, "list"

    kept, newly = [], []
    for it in items:
        u = it.get(URL_KEY)
        if not u:
            kept.append(it)              # URLが取れないものは残す
            continue
        if u in seen:
            continue                     # 既出 → 除外
        kept.append(it)
        newly.append(u)

    for u in newly:                      # 新規を台帳に追記
        posted.append({"url": u, "seen_at": now.isoformat()})
        seen.add(u)

    cutoff = now - timedelta(days=RETENTION_DAYS)   # 古い台帳を掃除
    def recent(e):
        try:
            return datetime.fromisoformat(e["seen_at"]) >= cutoff
        except (KeyError, ValueError):
            return True
    posted = [e for e in posted if recent(e)]

    out = (feeds | {"items": kept}) if container == "dict" else kept
    FEEDS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps({"posted": posted}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"除外(既出): {len(items)-len(kept)}件 / 残す: {len(kept)}件 / 台帳: {len(posted)}件")

if __name__ == "__main__":
    main()

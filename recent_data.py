"""Bounded, cached reads of documented KICKBASE performance/transfer data.

Schema: kickflow/src/api/kickbase/schemas.ts and mappers.ts (2026-09-15).
Per-game points are p, minutes mp (e.g. "90'"); ap/tp are season totals.
"""
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from base_xi import number, read_cache, write_cache
from decision_engine import player_id


def timestamp(value):
    if isinstance(value, (int, float)):
        return number(value)
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc).timestamp() if d.tzinfo is None else d.timestamp()
    except ValueError:
        return None


def season_label(now):
    d = datetime.fromtimestamp(now, timezone.utc)
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y}/{str(y+1)[-2:]}"


def parse_performance(payload, now):
    seasons = payload.get("it", []) if isinstance(payload, dict) else []
    if not isinstance(seasons, list):
        return [], []
    label = season_label(now)
    valid_titles = {label, label[2:], label.replace("/", "-"), f"{label[:4]}/{int(label[:4])+1}"}
    past, future = {}, {}
    for season in seasons:
        if not isinstance(season, dict):
            continue
        # Never fold prior-season rows into current form. Unknown season names
        # require a date in the current season, not an assumed API ordering.
        title_ok = str(season.get("ti", "")).strip() in valid_titles
        for row in season.get("ph", []) if isinstance(season.get("ph"), list) else []:
            if not isinstance(row, dict):
                continue
            dt = timestamp(row.get("md"))
            if not (title_ok or (dt and season_label(dt) == label)):
                continue
            day = number(row.get("day"))
            if day is None or not 1 <= day <= 40:
                continue
            minute = row.get("mp")
            if isinstance(minute, str) and re.fullmatch(r"\d{1,3}['’]?", minute.strip()):
                minute = number(minute.strip().rstrip("'’"))
            elif not isinstance(minute, (int, float)):
                minute = None
            minute = number(minute)
            minute = minute if minute is not None and 0 <= minute <= 130 else None
            item = {"day": int(day), "date": row.get("md"), "timestamp": dt,
                    "minutes": minute, "points": number(row.get("p")),
                    "home": str(row.get("t1", "")), "away": str(row.get("t2", "")),
                    "team": str(row.get("pt", "")), "season": label}
            played = row.get("t1g") is not None and row.get("t2g") is not None
            if played and (dt is None or dt <= now-3*3600):
                past[int(day)] = item
            elif not played and dt and dt > now:
                future[int(day)] = item
    return [past[k] for k in sorted(past)][-5:], sorted(future.values(), key=lambda x: x["timestamp"])[:3]


def enrich_recent(client, league_id, players, data_dir, now=None):
    now = time.time() if now is None else now
    path = Path(data_dir) / "recent_performance.json"
    cache = read_cache(path)
    output, calls = [], 0
    # Oldest requested entries first prevents starvation when the market changes.
    ordered = sorted({player_id(p) for p in players if player_id(p)},
                     key=lambda pid: cache.get(pid, {}).get("attempted", 0))
    for pid in ordered:
        entry = cache.get(pid, {})
        if now - entry.get("attempted", 0) < 3600 or calls >= 4:
            continue
        calls += 1
        response = client.get_optional(f"/v4/leagues/{quote(str(league_id), safe='')}/players/{quote(pid, safe='')}/performance")
        entry["attempted"] = now
        if response.get("ok"):
            past, future = parse_performance(response.get("data"), now)
            if past or future:
                entry.update(rows=past, upcoming=future, checked_at=now)
        cache[pid] = entry
    write_cache(path, cache)
    for p in players:
        entry = cache.get(player_id(p), {})
        fresh = 0 <= now - entry.get("checked_at", 0) <= 6 * 3600
        output.append({**p, "recent": {"available": fresh, "source": "KICKBASE performance",
                       "checked_at": entry.get("checked_at"), "rows": entry.get("rows", []) if fresh else [],
                       "upcoming": entry.get("upcoming", []) if fresh else []}})
    return output


def purchase_details(client, league_id, squad, user_id, data_dir, now=None):
    now = time.time() if now is None else now
    path = Path(data_dir) / "purchase_history.json"
    cache = read_cache(path)
    calls = 0
    for p in sorted(squad, key=lambda p: cache.get(player_id(p), {}).get("attempted", 0)):
        pid = player_id(p)
        entry = cache.get(pid, {})
        if pid and calls < 3 and now - entry.get("attempted", 0) >= 3600:
            calls += 1
            r = client.get_optional(f"/v4/leagues/{quote(str(league_id), safe='')}/players/{quote(pid, safe='')}/transferHistory")
            entry["attempted"] = now
            if r.get("ok") and isinstance(r.get("data"), dict):
                rows = [x for x in r["data"].get("it", []) if isinstance(x, dict) and timestamp(x.get("dt"))]
                latest = max(rows, key=lambda x: timestamp(x["dt"]), default={})
                buyer = latest.get("u")
                buyer = buyer.get("i") if isinstance(buyer, dict) else buyer
                if str(buyer) == str(user_id) and (number(latest.get("trp")) or 0) > 0:
                    entry.update(price=number(latest["trp"]), acquired_at=timestamp(latest["dt"]), checked_at=now)
                else:
                    entry = {"attempted": now}
            cache[pid] = entry
    write_cache(path, cache)
    out = []
    for p in squad:
        e = cache.get(player_id(p), {})
        current = 0 <= now - e.get("checked_at", 0) <= 6 * 3600
        out.append({**p, "acquisition": {"price": e.get("price") if current else None,
                    "time": e.get("acquired_at") if current else None,
                    "source": "KICKBASE transferHistory" if current else "unbekannt"}})
    return out

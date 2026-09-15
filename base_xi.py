"""Read Base-XI's public player database; no credentials or browser cookies.

Schema verified against /api/players?comp=1 on 2026-09-15. Historical starts
are counts, not a future starting probability. Form points are not minutes.
"""
import json
import math
import time
from pathlib import Path

import requests

URL = "https://www.base-xi.de/api/players"


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def read_cache(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_cache(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def fetch_base_xi(data_dir, config, session=None, now=None):
    now = time.time() if now is None else now
    result = {"source": "Base-XI", "url": "https://www.base-xi.de/players",
              "available": False, "players": {}, "status": "deaktiviert"}
    if not config.get("base_xi_enabled", True):
        return result
    comp = str(config.get("base_xi_competition", "1"))
    if comp not in ("1", "2"):
        return {**result, "status": "Ungültiger Wettbewerb"}
    path = Path(data_dir) / ("base_xi_" + comp + ".json")
    cache = read_cache(path)
    ttl = max(6, float(config.get("base_xi_refresh_hours", 6))) * 3600
    fetched = number(cache.get("fetched_at"))
    attempted = number(cache.get("attempted_at"))
    fresh = fetched is not None and 0 <= now - fetched < ttl
    # Failed requests also back off for an hour (including HTTP 429).
    if not fresh and (attempted is None or now - attempted >= 3600):
        cache["attempted_at"] = now
        try:
            response = (session or requests).get(URL, params={"comp": comp}, timeout=20)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows or not all(
                isinstance(p, dict) and str(p.get("id", "")).isdigit()
                and number(p.get("marketValue")) is not None for p in rows
            ):
                raise ValueError("Spielerdaten-Schema nicht erkannt")
            cache.update(players={str(p["id"]): p for p in rows}, fetched_at=now, error=None)
            fresh = True
        except (requests.RequestException, ValueError) as exc:
            cache["error"] = type(exc).__name__
        write_cache(path, cache)
    return {**result, "available": fresh and bool(cache.get("players")),
            "players": cache.get("players", {}) if fresh else {},
            "checked_at": cache.get("fetched_at"), "cached": fresh and fetched == cache.get("fetched_at"),
            "status": "ok" if fresh else "Nicht verfügbar oder veraltet; keine neuen Scouting-Käufe",
            "error": cache.get("error")}


def enrich_base_xi(players, source):
    output = []
    index = source.get("players", {}) if source.get("available") else {}
    for original in players:
        p = dict(original)
        pid = str(p.get("id") or p.get("i") or p.get("playerId") or p.get("pi") or "")
        raw = index.get(pid)
        p["base_xi"] = {"available": False}
        if raw:
            bx = {"available": True, "checked_at": source.get("checked_at"),
                  "name": raw.get("name"), "source": "Base-XI",
                  "is_hot": raw.get("isHot") is True,
                  "gamble": raw.get("gamble"), "momentum": raw.get("momentum"),
                  "next_match": raw.get("next_match"), "match_preview": raw.get("match_preview"),
                  "status_text": raw.get("statusText"),
                  "median_source": raw.get("consistencyFrom"),
                  "ppm_source": raw.get("pointsPerMioFrom"),
                  "previous_season": raw.get("prevSeasonLabel")}
            bx["form"] = raw.get("detail_form")
            bx["form_checked_at"] = raw.get("detail_checked_at")
            for target, field in {
                "market_value": "marketValue", "trend_24h": "mvTrend", "trend_7d": "trend7d",
                "ki_trend": "kiTrend", "fair_value": "fairValue", "average_points": "avgPoints",
                "median_points": "medianPoints", "points_per_million": "pointsPerMio",
                "matches": "matchesPlayed", "starts": "starts", "average_minutes": "avgMinutes",
                "status": "status", "total_points": "totalPoints",
                "previous_average": "avgPrevSeason", "previous_matches": "gamesPrevSeason",
            }.items():
                bx[target] = number(raw.get(field))
            mv, fv = bx["market_value"], bx["fair_value"]
            bx["is_deal"] = bool(mv and fv and mv < fv * 0.7)
            p["base_xi"] = bx
            # Only fill missing raw values, never overwrite owner, offers or buy price.
            if not number(p.get("marketValue")) and not number(p.get("mv")):
                p["mv"] = mv
            perf = dict(p.get("performance") or {})
            for key in ("average_points", "total_points"):
                if perf.get(key) is None:
                    perf[key] = bx[key]
            perf["base_xi"] = True
            p["performance"] = perf
        output.append(p)
    return output


def fetch_base_xi_forms(source, players, data_dir, config, session=None, now=None):
    """Gradually fetch the same public detail JSON used by Base-XI's player modal.

    At most two requests per poll; each detail is cached for six hours. Do not
    present points as minutes or merge a previous season into current form.
    """
    if not source.get("available"):
        return source
    now = time.time() if now is None else now
    comp = str(config.get("base_xi_competition", "1"))
    path = Path(data_dir) / ("base_xi_forms_" + comp + ".json")
    cache = read_cache(path)
    count = 0
    ttl = 6 * 3600
    for p in players:
        pid = str(p.get("id") or p.get("i") or p.get("playerId") or p.get("pi") or "")
        if not pid.isdigit() or pid not in source["players"]:
            continue
        entry = cache.get(pid, {})
        fresh = 0 <= now - entry.get("fetched_at", -ttl) < ttl
        if not fresh and count < 2 and now - entry.get("attempted_at", -3600) >= 3600:
            count += 1
            entry["attempted_at"] = now
            try:
                response = (session or requests).get(
                    "https://www.base-xi.de/api/modal/player/" + pid,
                    params={"comp": comp}, timeout=15)
                response.raise_for_status()
                payload = response.json()
                detail = payload.get("data", {})
                if payload.get("success") is not True or str(detail.get("id")) != pid or not isinstance(detail.get("form"), list):
                    raise ValueError("Unerwartete Formdaten")
                entry.update(form=detail["form"], fetched_at=now)
                fresh = True
            except (requests.RequestException, ValueError, AttributeError):
                pass
            cache[pid] = entry
            write_cache(path, cache)
        if fresh:
            source["players"][pid]["detail_form"] = entry.get("form")
            source["players"][pid]["detail_checked_at"] = entry.get("fetched_at")
    return source

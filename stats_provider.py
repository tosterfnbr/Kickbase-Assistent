"""Performance enrichment from KICKBASE fields and optional public Kickbest data."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests

from decision_engine import normalize_name, player_name, pick

JSON_SCRIPT_RE = re.compile(r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>', re.I | re.S)


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _number(obj, *keys):
    value = pick(obj, *keys, default=None)
    try:
        return float(value) if value is not None and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def _kickbest_index(html):
    index = {}
    for raw in JSON_SCRIPT_RE.findall(html):
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in _walk(payload):
            name = pick(item, "name", "playerName", "fullName", default="")
            key = normalize_name(name)
            if key and len(key.split()) >= 2:
                index[key] = item
    return index


def fetch_kickbest(players, config, session=None):
    result = {
        "source": "Kickbest", "url": str(config.get("kickbest_url", "https://kickbest.app/")),
        "checked_at": datetime.now(timezone.utc).isoformat(), "available": False,
        "matched": 0, "players": {}, "status": "deaktiviert",
    }
    if not config.get("kickbest_enabled", True):
        return result
    session = session or requests.Session()
    session.headers.update({"User-Agent": "KickbaseAssistent/1.0"})
    try:
        response = session.get(result["url"], timeout=15)
        response.raise_for_status()
        index = _kickbest_index(response.text)
        for player in players:
            key = normalize_name(player_name(player))
            item = index.get(key)
            if not item:
                continue
            result["players"][key] = {
                "average_points": _number(item, "averagePoints", "avgPoints", "pointsAverage"),
                "total_points": _number(item, "totalPoints", "points"),
                "games": _number(item, "games", "appearances", "matches"),
                "market_value_change": _number(item, "marketValueChange", "valueChange"),
                "raw_points": _number(item, "rawPoints", "basePoints"),
            }
        result["matched"] = len(result["players"])
        result["available"] = bool(index)
        result["status"] = "ok" if index else "keine öffentlichen strukturierten Spielerdaten"
    except requests.RequestException as exc:
        result["status"] = f"nicht verfügbar: {type(exc).__name__}"
    return result


def enrich_performance(players, kickbest):
    external = kickbest.get("players", {}) if isinstance(kickbest, dict) else {}
    output = []
    for original in players:
        player = dict(original)
        ext = external.get(normalize_name(player_name(player)), {})
        average = ext.get("average_points") if ext.get("average_points") is not None else _number(player, "averagePoints", "avgPoints", "ap", "average")
        total = ext.get("total_points") if ext.get("total_points") is not None else _number(player, "totalPoints", "points", "tp")
        games = ext.get("games") if ext.get("games") is not None else _number(player, "games", "appearances", "matches", "gm")
        value = _number(player, "marketValue", "mv") or 0
        ppm = (average / (value / 1_000_000)) if average is not None and value > 0 else None
        player["performance"] = {
            "average_points": average,
            "total_points": total,
            "games": games,
            "points_per_million": ppm,
            "raw_points": ext.get("raw_points"),
            "market_value_change": ext.get("market_value_change"),
            "source": "Kickbest" if ext else "KICKBASE",
        }
        output.append(player)
    return output

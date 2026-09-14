"""Conservative LigaInsider forecast reader.

The scraper only upgrades a player when the name occurs inside the forecast
section. Network/markup failures produce 'unavailable', never a zero S11 score.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

import requests

from decision_engine import normalize_name, player_name

BASE = "https://www.ligainsider.de/"
TEAM_LINK_RE = re.compile(r'href=["\']([^"\']+/(?:\d+)/?)["\']', re.I)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def _text(html):
    html = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", html, flags=re.I | re.S)
    return SPACE_RE.sub(" ", unescape(TAG_RE.sub(" ", html))).strip()


def _forecast_segment(html):
    text = _text(html)
    start = text.casefold().find("voraussichtliche aufstellung")
    if start < 0:
        return ""
    segment = text[start:start + 9000]
    endings = ("ausfälle", "nicht berücksichtigt", "letzte spiele", "ergebnisse für alle wettbewerbe")
    positions = [segment.casefold().find(marker, 80) for marker in endings]
    positions = [pos for pos in positions if pos > 0]
    return segment[:min(positions)] if positions else segment


def _discover_team_urls(session):
    response = session.get(BASE + "bundesliga/", timeout=15)
    response.raise_for_status()
    urls = []
    for href in TEAM_LINK_RE.findall(response.text):
        url = urljoin(BASE, href.split("?")[0])
        if url not in urls and "ligainsider_" not in url:
            urls.append(url)
    return urls[:18]


def fetch_ligainsider(players, config, session=None):
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {"available": False, "checked_at": checked_at, "source": "LigaInsider", "players": {}, "errors": []}
    if not config.get("ligainsider_enabled", True):
        result["status"] = "deaktiviert"
        return result
    session = session or requests.Session()
    session.headers.update({"User-Agent": "KickbaseAssistent/1.0 (+private fantasy tool)"})
    urls = list(config.get("ligainsider_team_urls") or [])
    try:
        if not urls:
            urls = _discover_team_urls(session)
        segments = []
        for url in urls:
            try:
                response = session.get(url, timeout=15)
                response.raise_for_status()
                segment = _forecast_segment(response.text)
                if segment:
                    segments.append(normalize_name(segment))
            except requests.RequestException as exc:
                result["errors"].append(f"{url}: {type(exc).__name__}")
        for player in players:
            name = normalize_name(player_name(player))
            if not name:
                continue
            surname = name.split()[-1]
            full_match = any(name in segment for segment in segments)
            surname_match = len(surname) >= 5 and sum(surname in segment for segment in segments) == 1
            if full_match or surname_match:
                result["players"][name] = {"score": 5, "status": "voraussichtliche Startelf"}
        result["available"] = bool(segments)
        result["status"] = "ok" if segments else "keine verwertbaren Aufstellungen"
    except requests.RequestException as exc:
        logging.warning("LigaInsider nicht verfügbar: %s", exc)
        result["errors"].append(type(exc).__name__)
        result["status"] = "nicht verfügbar"
    return result

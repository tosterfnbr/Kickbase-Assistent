import argparse
import csv
import json
import logging
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from xml.etree import ElementTree

import keyring
import requests

from decision_engine import build_trade_plan, best_lineup, enrich_s11, pick as engine_pick, player_id as engine_player_id, player_name as engine_player_name, s11_score
from ligainsider import fetch_ligainsider

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LOG = ROOT / "kickbase-assistent.log"
API = "https://api.kickbase.com"
APP = "KickbaseAssistent"

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")


class KickbaseClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Kickbase/4.0.0"})

    def login(self, email, password):
        response = self.session.post(
            f"{API}/v4/user/login",
            json={"em": email, "pass": password, "loy": False, "rep": {}},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("tkn")
        if not token:
            raise RuntimeError("KICKBASE hat kein Zugriffstoken zurückgegeben.")
        self.session.headers["Authorization"] = f"Bearer {token}"
        return payload

    def get(self, *paths):
        last = None
        for path in paths:
            response = self.session.get(API + path, timeout=20)
            last = response
            if response.ok:
                return response.json()
        last.raise_for_status()

    def write(self, method, path, payload=None):
        """Send one authenticated write request and return a compact receipt."""
        response = self.session.request(method, API + path, json=payload, timeout=20)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            body = {}
        return {"status": response.status_code, "body": body}

    def get_optional(self, *paths):
        for path in paths:
            try:
                response = self.session.get(API + path, timeout=20)
                if response.ok:
                    return {"ok": True, "path": path, "data": response.json()}
            except (requests.RequestException, ValueError):
                continue
        return {"ok": False, "path": paths[0] if paths else "", "data": {}}


def list_from(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("leagues", "it", "items", "players", "market"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def pick(obj, *keys, default=""):
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            return obj[key]
    return default


def walk_dicts(value):
    """Yield every dictionary in a nested API response."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def find_named_league(payload, wanted):
    """The undocumented API has used several wrappers; match by league name."""
    for item in walk_dicts(payload):
        name = pick(item, "name", "n", "leagueName", "ln", default=None)
        item_id = pick(item, "id", "i", "leagueId", "li", default=None)
        if name is not None and item_id is not None and str(name).casefold() == wanted:
            return item
    return None


def find_number(payload, *keys):
    for item in walk_dicts(payload):
        for key in keys:
            value = item.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
    return None


def bundesliga_live():
    """Load public Bundesliga schedule data; a failure must never stop KICKBASE sync."""
    try:
        group_response = requests.get("https://api.openligadb.de/getcurrentgroup/bl1", timeout=12)
        group_response.raise_for_status()
        group = group_response.json()
        group_order = int(group.get("groupOrderID") or 0)
        now = datetime.now(timezone.utc)
        season = now.year if now.month >= 7 else now.year - 1
        matches = []
        for group_id in (group_order, group_order + 1):
            response = requests.get(
                f"https://api.openligadb.de/getmatchdata/bl1/{season}/{group_id}", timeout=12
            )
            if response.ok:
                matches.extend(response.json())

        def kickoff(match):
            raw = match.get("matchDateTimeUTC") or match.get("matchDateTime")
            if not raw:
                return None
            try:
                value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                return None

        upcoming = sorted(
            (match for match in matches if kickoff(match) and kickoff(match) > now),
            key=kickoff,
        )
        next_match = upcoming[0] if upcoming else None
        next_group = next_match.get("group", {}) if next_match else {}
        return {
            "available": True,
            "matchday": next_group.get("groupOrderID") or group_order,
            "matchday_name": next_group.get("groupName") or group.get("groupName"),
            "next_kickoff": kickoff(next_match).isoformat() if next_match else None,
            "matches": matches,
            "source": "OpenLigaDB",
        }
    except (requests.RequestException, ValueError, TypeError) as exc:
        logging.warning("Bundesliga-Livedaten nicht verfügbar: %s", exc)
        return {"available": False, "matches": [], "source": "OpenLigaDB"}


def update_value_history(stamp, squad_value):
    history_path = DATA / "marktwert_verlauf.json"
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except (OSError, ValueError):
        history = []
    if isinstance(squad_value, (int, float)):
        history.append({"time": stamp, "value": round(squad_value)})
    history = history[-96:]
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history


def player_list(payload):
    """Find the most likely player collection inside the compact API response."""
    candidates = []
    for item in walk_dicts(payload):
        for key in ("players", "it", "lineup", "pl"):
            value = item.get(key)
            if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
                if any(pick(row, "id", "i", "playerId", "pi", default=None) for row in value):
                    candidates.append(value)
    return max(candidates, key=len, default=[])


def trade_log(entry):
    DATA.mkdir(exist_ok=True)
    path = DATA / "handelslog.json"
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            entries = []
    except (OSError, ValueError):
        entries = []
    entries.append(entry)
    path.write_text(json.dumps(entries[-300:], ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def display_name(player):
    return " ".join(str(value) for value in (
        pick(player, "firstName", "fn"), pick(player, "lastName", "n", "name")
    ) if value).strip()


def detect_new_market_players(players):
    """Return genuinely new market entries; the first sync only establishes a baseline."""
    path = DATA / "markt_gesehen.json"
    old = load_json(path, {})
    previous = {str(item) for item in old.get("ids", [])} if isinstance(old, dict) else set()
    current = {str(pick(player, "id", "i", "playerId", "pi")) for player in players}
    new_players = [] if not previous else [
        player for player in players
        if str(pick(player, "id", "i", "playerId", "pi")) not in previous
    ]
    save_json(path, {"updated_at": datetime.now(timezone.utc).isoformat(), "ids": sorted(current)})
    return new_players


RISK_WORDS = (
    "verletzt", "verletzung", "angeschlagen", "fällt aus", "ausfall", "fraglich",
    "muskulär", "krank", "sperre", "gesperrt", "rotation", "bank", "startelf",
    "nicht im kader", "trainingsabbruch", "operation",
)


def news_datetime(item):
    """Return the source publication time, never the later discovery time when available."""
    for raw in (item.get("published_at"), item.get("published"), item.get("detected_at")):
        if not raw:
            continue
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            try:
                value = parsedate_to_datetime(str(raw))
            except (TypeError, ValueError, OverflowError):
                continue
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def news_monitor(players, config):
    """Collect fresh public news/X risk hints without treating them as confirmed facts."""
    path = DATA / "news_feed.json"
    state = load_json(path, {"checked_at": None, "items": [], "seen": []})
    if not config.get("news_monitor", True):
        return state, []
    now = datetime.now(timezone.utc)
    max_age = max(12, min(168, int(config.get("news_max_age_hours", 72))))
    cutoff = now.timestamp() - max_age * 3600
    cached_items = [
        item for item in state.get("items", [])
        if isinstance(item, dict) and news_datetime(item) and news_datetime(item).timestamp() >= cutoff
    ]
    cached_items.sort(key=lambda item: news_datetime(item).timestamp(), reverse=True)
    state["items"] = cached_items
    checked = state.get("checked_at") if isinstance(state, dict) else None
    if checked:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(checked.replace("Z", "+00:00"))).total_seconds()
            if age < max(15, int(config.get("news_poll_minutes", 60))) * 60:
                save_json(path, state)
                return state, []
        except (TypeError, ValueError):
            pass
    names = [display_name(player) for player in players if display_name(player)][:18]
    seen = set(state.get("seen", [])) if isinstance(state, dict) else set()
    found = []
    detected_at = datetime.now(timezone.utc).isoformat()
    chunks = [names[index:index + 6] for index in range(0, len(names), 6)]
    for chunk in chunks[:3]:
        query = " OR ".join(f'\"{name}\"' for name in chunk) + " (Verletzung OR Startelf OR Rotation OR Ausfall) Bundesliga when:3d"
        try:
            response = requests.get(
                "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=de&gl=DE&ceid=DE:de",
                timeout=15,
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            for item in root.findall(".//item")[:15]:
                title = (item.findtext("title") or "").strip()
                description = (item.findtext("description") or "").strip()
                link = (item.findtext("link") or "").strip()
                published = (item.findtext("pubDate") or "").strip()
                text = f"{title} {description}".casefold()
                player_name = next((name for name in chunk if name.casefold().split()[-1] in text), "")
                candidate = {"published": published}
                source_time = news_datetime(candidate)
                if link and player_name and source_time and source_time.timestamp() >= cutoff and any(word in text for word in RISK_WORDS):
                    found.append({"id": link, "source": "Google News", "player": player_name, "title": title, "url": link, "published": published, "published_at": source_time.astimezone(timezone.utc).isoformat(), "detected_at": detected_at})
        except (requests.RequestException, ElementTree.ParseError) as exc:
            logging.warning("News-Abfrage fehlgeschlagen: %s", exc)

    x_token = keyring.get_password(APP, "x_bearer_token")
    if config.get("x_monitor") and x_token and names:
        query_names = " OR ".join(f'\"{name}\"' for name in names[:8])
        query = f"({query_names}) (verletzt OR Ausfall OR Startelf OR Rotation) lang:de -is:retweet"
        try:
            response = requests.get(
                "https://api.x.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {x_token}"},
                params={"query": query, "max_results": 10, "tweet.fields": "created_at"},
                timeout=15,
            )
            response.raise_for_status()
            for post in response.json().get("data", []):
                text = str(post.get("text", ""))
                player_name = next((name for name in names[:8] if name.casefold().split()[-1] in text.casefold()), "")
                if player_name:
                    post_id = str(post.get("id", ""))
                    candidate = {"published": post.get("created_at", "")}
                    source_time = news_datetime(candidate)
                    if source_time and source_time.timestamp() >= cutoff:
                        found.append({"id": "x:" + post_id, "source": "X", "player": player_name, "title": text[:280], "url": f"https://x.com/i/web/status/{post_id}", "published": post.get("created_at", ""), "published_at": source_time.astimezone(timezone.utc).isoformat(), "detected_at": detected_at})
        except (requests.RequestException, ValueError) as exc:
            logging.warning("X-Abfrage fehlgeschlagen: %s", exc)

    unique = {item["id"]: item for item in found}
    new_items = [item for item in unique.values() if item["id"] not in seen]
    combined = new_items + cached_items
    combined.sort(key=lambda item: news_datetime(item).timestamp(), reverse=True)
    combined = combined[:100]
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "items": combined, "seen": list((seen | set(unique)))[-500:]}
    save_json(path, result)
    return result, new_items


def send_email(config, subject, lines):
    recipient = str(config.get("notification_email", "")).strip()
    username = str(config.get("smtp_username", "")).strip()
    password = keyring.get_password(APP, "smtp_password")
    if not config.get("email_notifications") or not recipient or not username or not password:
        return {"sent": False, "reason": "E-Mail nicht eingerichtet"}
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = recipient
    message.set_content("\n".join(lines))
    try:
        host = str(config.get("smtp_host", "smtp.gmail.com"))
        port = int(config.get("smtp_port", 465))
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
            server.login(username, password)
            server.send_message(message)
        return {"sent": True, "time": datetime.now(timezone.utc).isoformat()}
    except (OSError, smtplib.SMTPException) as exc:
        logging.warning("E-Mail konnte nicht gesendet werden: %s", exc)
        return {"sent": False, "reason": str(exc)[:200]}


def seconds_until_kickoff(live):
    raw = live.get("next_kickoff") if isinstance(live, dict) else None
    if not raw:
        return None
    try:
        return (datetime.fromisoformat(str(raw).replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return None


def normalized_squad(extra, market_players, user_id=""):
    """Merge the current user's roster fragments so values/photos are not lost."""
    sources = []
    for key in ("me", "lineup"):
        sources.extend(player_list(extra.get(key, {})))
    users = extra.get("users", {})
    for item in walk_dicts(users):
        item_id = str(pick(item, "id", "i", "userId", "ui", "u", default=""))
        if user_id and item_id == str(user_id):
            sources.extend(player_list(item))
    by_id = {}
    for player in sources:
        player_id = str(pick(player, "id", "i", "playerId", "pi", default=""))
        if player_id:
            by_id[player_id] = {**by_id.get(player_id, {}), **player}
    for player in market_players:
        player_id = str(pick(player, "id", "i", "playerId", "pi", default=""))
        if player_id in by_id:
            by_id[player_id] = {**by_id[player_id], **player}
    return list(by_id.values())


def run_trading(client, league_id, market_players, extra, config, live, user_id="", news_items=None):
    """Plan in observe mode; execute the exact same bounded plan only in live mode."""
    stamp = datetime.now(timezone.utc).isoformat()
    live_mode = bool(config.get("trading_enabled")) and config.get("mode") == "live"
    max_actions = max(1, min(5, int(config.get("max_actions_per_run", 1))))
    min_cash = max(0, int(config.get("minimum_cash", 1_000_000)))
    max_overpay = max(0, min(30, float(config.get("maximum_overpay_percent", 8))))
    protect_hours = max(0, int(config.get("matchday_protection_hours", 48)))
    budget = find_number(extra.get("me", {}), "budget", "b", "cash", "bal")
    squad = normalized_squad(extra, market_players, user_id)
    # Prefer already enriched objects supplied by run_once.
    enriched_by_id = {engine_player_id(p): p for p in market_players + config.get("_enriched_squad", [])}
    squad = [enriched_by_id.get(engine_player_id(p), p) for p in squad]
    near_matchday = (seconds_until_kickoff(live) or 10**12) <= protect_hours * 3600
    plan = build_trade_plan(market_players, squad, config, user_id, near_matchday, budget)
    result = {
        "enabled": bool(config.get("trading_enabled")),
        "mode": "live" if live_mode else "observe",
        "status": "Aktiv" if live_mode else "Testmodus",
        "actions": [],
        "planned": [],
        "blocked": list(plan["blocked"]),
        "best_lineup": plan["lineup"],
    }

    risky_names = set()
    risk_hours = max(1, int(config.get("risk_news_hours", 36)))
    for item in news_items or []:
        source_time = news_datetime(item) if isinstance(item, dict) else None
        if source_time and (datetime.now(timezone.utc) - source_time).total_seconds() <= risk_hours * 3600:
            name = str(item.get("player", "")).casefold().strip()
            if name:
                risky_names.add(name)
                risky_names.add(name.split()[-1])

    def compact(action):
        player = action.get("player", {})
        return {
            "time": stamp,
            "action": action["kind"],
            "player_id": engine_player_id(player),
            "player": engine_player_name(player),
            "reason": action.get("reason", ""),
            "amount": action.get("amount"),
        }

    # Add late-buy proposals using corrected S11 semantics. Unknown never means 0/5.
    own_id = str(user_id or config.get("user_id", ""))
    targets = {str(item) for item in config.get("targets", [])}
    target_names = {str(item).casefold().strip() for item in config.get("watchlist_names", []) if str(item).strip()}
    min_s11 = max(1, min(5, int(config.get("minimum_starting_probability", 3))))
    if config.get("auto_buy", True) and isinstance(budget, (int, float)):
        buy_candidates = []
        for player in market_players:
            pid = engine_player_id(player)
            if own_id and str(pick(player, "userId", "ui", "u", default="")) == own_id:
                continue
            mv = int(pick(player, "marketValue", "mv", default=0) or 0)
            price = int(pick(player, "price", "prc", "p", default=mv) or mv)
            expiry = int(pick(player, "expiry", "exs", default=10**9) or 10**9)
            score = s11_score(player)
            name = engine_player_name(player).casefold()
            is_target = pid in targets or name in target_names
            if score is None:
                result["blocked"].append({"player_id": pid, "player": engine_player_name(player), "reason": "Kauf blockiert: S11-Chance unbekannt"})
                continue
            if mv <= 0 or score < min_s11 or (not is_target and int(pick(player, "marketValueTrend", "mvt", default=0) or 0) != 2):
                continue
            if expiry > int(config.get("bid_window_minutes", 10)) * 60:
                continue
            if name in risky_names or (name and name.split()[-1] in risky_names):
                result["blocked"].append({"player_id": pid, "player": engine_player_name(player), "reason": "Kauf wegen aktuellem Risiko-Hinweis blockiert"})
                continue
            bid = max(mv, price)
            if bid <= round(mv * (1 + max_overpay / 100)) and budget - bid >= min_cash:
                buy_candidates.append((not is_target, -score, expiry, {"kind": "buy", "player": player, "amount": bid, "reason": f"S11 {score}/5, Preis innerhalb der Grenze"}))
        plan["actions"].extend(item[-1] for item in sorted(buy_candidates))

    priority = {"accept_offer": 0, "buy": 1, "instant_sell": 2, "list": 3, "adjust_price": 4}
    selected = sorted(plan["actions"], key=lambda item: priority.get(item.get("kind"), 9))[:max_actions]
    result["planned"] = [compact(action) for action in selected]
    if not live_mode:
        result["status"] = f"Testmodus: {len(selected)} geplante Aktion(en)"
        return result

    for action in selected:
        player = action.get("player", {})
        pid = engine_player_id(player)
        try:
            if action["kind"] == "accept_offer":
                offer_id = str(pick(action["offer"], "offerId", "uoid", "id", "i"))
                client.write("POST", f"/v4/leagues/{league_id}/market/{pid}/offers/{offer_id}/accept", {})
            elif action["kind"] == "adjust_price":
                client.write("PUT", f"/v4/leagues/{league_id}/market/{pid}", {"price": action["amount"]})
            elif action["kind"] == "instant_sell":
                client.write("POST", f"/v4/leagues/{league_id}/market/{pid}/sell", {})
            elif action["kind"] == "list":
                client.write("POST", f"/v4/leagues/{league_id}/market/{pid}", {"price": action["amount"]})
            elif action["kind"] == "buy":
                client.write("POST", f"/v4/leagues/{league_id}/market/{pid}/offers", {"price": action["amount"]})
            entry = {**compact(action), "ok": True}
        except requests.RequestException as exc:
            entry = {**compact(action), "ok": False, "error": str(exc)[:240]}
        result["actions"].append(entry)
        trade_log(entry)
    result["status"] = f"{sum(1 for item in result['actions'] if item['ok'])} Aktion(en) ausgeführt"
    return result


def run_once():
    email = keyring.get_password(APP, "email")
    password = keyring.get_password(APP, "password")
    if not email or not password:
        raise RuntimeError("Keine lokalen Zugangsdaten gefunden. Bitte INSTALLIEREN.bat erneut starten.")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    client = KickbaseClient()
    login = client.login(email, password)
    wanted = config["league_name"].casefold()
    league = find_named_league(login, wanted)
    leagues_raw = login
    if not league:
        leagues_raw = client.get("/v4/leagues", "/v4/user/leagues")
        league = find_named_league(leagues_raw, wanted)
    if not league:
        names = sorted({
            str(pick(x, "name", "n", "leagueName", "ln"))
            for x in walk_dicts(leagues_raw)
            if pick(x, "name", "n", "leagueName", "ln", default=None) is not None
        })
        names = ", ".join(names) if names else "keine Liga in der Antwort"
        raise RuntimeError(f"Liga '{config['league_name']}' nicht gefunden. Gefunden: {names}")
    league_id = pick(league, "id", "i", "leagueId", "li")
    market_raw = client.get(f"/v4/leagues/{league_id}/market", f"/v4/league/{league_id}/market")
    players = list_from(market_raw)
    extra = {
        "me": client.get_optional(f"/v4/leagues/{league_id}/me", f"/v4/league/{league_id}/me"),
        "info": client.get_optional(f"/v4/leagues/{league_id}/info", f"/v4/league/{league_id}/info"),
        "lineup": client.get_optional(f"/v4/leagues/{league_id}/lineup", f"/v4/league/{league_id}/lineup"),
        "users": client.get_optional(f"/v4/leagues/{league_id}/users", f"/v4/league/{league_id}/users"),
        "stats": client.get_optional(f"/v4/leagues/{league_id}/stats", f"/v4/league/{league_id}/stats"),
        "feed": client.get_optional(f"/v4/leagues/{league_id}/feed?start=0", f"/v4/league/{league_id}/feed?start=0")
    }
    DATA.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with (DATA / "markt.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Zeitpunkt_UTC", "Spieler_ID", "Name", "Marktwert", "Preis", "Ablauf"])
        for player in players:
            writer.writerow([
                stamp,
                pick(player, "id", "i"),
                pick(player, "name", "n", "firstName"),
                pick(player, "marketValue", "mv"),
                pick(player, "price", "p"),
                pick(player, "expiry", "exs", "dt"),
            ])
    squad_value = find_number(extra.get("me", {}), "teamValue", "squadValue", "tv")
    history = update_value_history(stamp, squad_value)
    live = bundesliga_live()
    new_players = detect_new_market_players(players)
    user_id = pick(login, "id", "i", "userId", "ui", "u", default="")
    squad_players = normalized_squad(extra, players, user_id)
    ligainsider = fetch_ligainsider(squad_players + players, config)
    players = enrich_s11(players, ligainsider)
    squad_players = enrich_s11(squad_players, ligainsider)
    config["_enriched_squad"] = squad_players
    recommended_lineup = best_lineup(squad_players)
    watched_players = [{"name": name} for name in config.get("watchlist_names", []) if str(name).strip()]
    news, new_news = news_monitor(squad_players + players + watched_players, config)
    trading = run_trading(client, league_id, players, extra, config, live, user_id, news.get("items", []))
    notification_lines = []
    if new_players:
        watched_names = {str(name).casefold().strip() for name in config.get("watchlist_names", [])}
        notification_lines.extend(["NEU AUF DEM TRANSFERMARKT:"] + [
            f"• {'⭐ BEOBACHTET: ' if display_name(player).casefold() in watched_names else ''}{display_name(player)} – Marktwert {int(pick(player, 'marketValue', 'mv', default=0) or 0):,} €"
            for player in new_players
        ])
    if trading.get("actions"):
        notification_lines.extend(["", "AUTOMATISCHE HANDELSAKTIONEN:"] + [
            f"• {item['action']}: {item['player']} ({item['reason']})"
            for item in trading["actions"]
        ])
    if trading.get("blocked"):
        notification_lines.extend(["", "AUS SICHERHEIT BLOCKIERTE GEBOTE:"] + [
            f"• {item['player']}: {item['reason']}"
            for item in trading["blocked"]
        ])
    if new_news:
        notification_lines.extend(["", "NEUE STARTELF-/RISIKO-HINWEISE (BITTE QUELLE PRÜFEN):"] + [
            f"• {item['player']}: {item['title']}\n  {item['url']}"
            for item in new_news[:10]
        ])
    notification = (
        send_email(config, "KICKBASE Assistent – neue Ereignisse", notification_lines)
        if notification_lines else {"sent": False, "reason": "Keine neuen Ereignisse"}
    )
    snapshot = {"updated_at": stamp, "league": config["league_name"], "market": market_raw}
    (DATA / "letzter_markt.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {
        **snapshot,
        "league_id": league_id,
        "league_meta": league,
        "user_id": user_id,
        "squad": squad_players,
        "players": players,
        "best_lineup": recommended_lineup,
        "ligainsider": ligainsider,
        "sections": extra,
        "live": live,
        "value_history": history,
        "trading": trading,
        "new_market_players": new_players,
        "news": news,
        "notification": notification,
    }
    (DATA / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Markt erfolgreich aktualisiert: %s Einträge", len(players))
    print(f"Verbindung erfolgreich: {config['league_name']} – {len(players)} Markt-Einträge gespeichert.")
    print(f"Trading: {trading['status']}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if args.loop:
        while True:
            try:
                run_once()
            except Exception as exc:
                logging.exception("Aktualisierung fehlgeschlagen")
                print(f"Fehler: {exc}")
            config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            time.sleep(max(5, int(config.get("poll_minutes", 15))) * 60)
    else:
        run_once()


if __name__ == "__main__":
    main()
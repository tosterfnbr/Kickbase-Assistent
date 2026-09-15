import argparse
import csv
import json
import logging
import math
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, quote_plus
from xml.etree import ElementTree

import keyring
import requests

from decision_engine import build_trade_plan, best_lineup, enrich_s11, pick as engine_pick, player_id as engine_player_id, player_name as engine_player_name, s11_score
from ligainsider import fetch_ligainsider
from stats_provider import enrich_performance, fetch_kickbest
from base_xi import fetch_base_xi, fetch_base_xi_forms, enrich_base_xi, number
from bid_policy import plan_bids, own_offer, login_user_id, identity
from notifications import hourly_digest
from recent_data import enrich_recent, purchase_details
from strategy import annotate, projection, choose_combination, expected
from portfolio import sync_portfolio, record_receipts, apply_exits, league_checks, report, shadow_trial

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
        if isinstance(body, dict) and (body.get("errMsg") or body.get("error") or body.get("success") is False):
            raise ValueError("KICKBASE hat den Auftrag abgelehnt: " + str(body.get("errMsg") or body.get("error") or "success=false")[:160])
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
        for key in ("players", "it", "lineup", "pl", "lp"):
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
    for key in ("me", "lineup", "squad"):
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


def hydrate_squad_details(client, league_id, players, config):
    """Cache authenticated player details so squad values and stats are complete."""
    DATA.mkdir(exist_ok=True)
    cache_path = DATA / "player_details.json"
    cache = load_json(cache_path, {})
    entries = cache.get("players", {}) if isinstance(cache, dict) else {}
    if not isinstance(entries, dict):
        entries = {}
    now = time.time()
    ttl = max(15, int(config.get("player_details_refresh_minutes", 60))) * 60
    output, changed = [], False
    for original in players:
        player = dict(original)
        pid = engine_player_id(player)
        entry = entries.get(pid, {}) if pid else {}
        cached = entry.get("data", {}) if isinstance(entry, dict) else {}
        if isinstance(cached, dict):
            player = {**cached, **player}
        fetched_at = entry.get("fetched_at", 0) if isinstance(entry, dict) else 0
        stale = not isinstance(fetched_at, (int, float)) or now - fetched_at >= ttl
        value = pick(player, "marketValue", "mv", default=0)
        if pid and (stale or not isinstance(value, (int, float)) or value <= 0):
            response = client.get_optional(f"/v4/leagues/{league_id}/players/{pid}")
            payload = response.get("data", {}) if response.get("ok") else {}
            detail = next((
                item for item in walk_dicts(payload)
                if str(pick(item, "id", "i", "playerId", "pi", default="")) == pid
            ), payload if isinstance(payload, dict) else {})
            if isinstance(detail, dict) and detail:
                player = {**player, **detail}
                entries[pid] = {"fetched_at": now, "data": detail}
                changed = True
        output.append(player)
    if changed:
        save_json(cache_path, {"updated_at": datetime.now(timezone.utc).isoformat(), "players": entries})
    return output


def run_trading(client, league_id, market_players, extra, config, live, user_id="", news_items=None):
    """Plan in observe mode; execute the exact same bounded plan only in live mode."""
    stamp = datetime.now(timezone.utc).isoformat()
    now = time.time()
    config = {**config, "_now": now, "_user_id":user_id}
    live_mode = bool(config.get("trading_enabled")) and config.get("mode") == "live"
    action_setting = config.get("portfolio_actions_per_run", 3) if config.get("portfolio_mode", True) else config.get("max_actions_per_run", 1)
    max_actions = max(1, min(5, int(action_setting)))
    protect_hours = max(0, int(config.get("matchday_protection_hours", 48)))
    budget = config["_budget"] if "_budget" in config else find_number(extra.get("me", {}), "budget", "b", "cash", "bal")
    squad = normalized_squad(extra, market_players, user_id)
    # Prefer already enriched objects supplied by run_once.
    enriched_by_id = {engine_player_id(p): p for p in market_players + config.get("_enriched_squad", [])}
    squad = [enriched_by_id.get(engine_player_id(p), p) for p in squad]
    if "_enriched_squad" in config:
        squad = config["_enriched_squad"]
    until_kickoff = seconds_until_kickoff(live)
    near_matchday = protect_hours>0 and (until_kickoff is None or until_kickoff <= protect_hours * 3600)
    DATA.mkdir(exist_ok=True)
    bid_state_path = DATA / "submitted_bids.json"
    bid_state = load_json(bid_state_path, {})
    bid_state = bid_state if isinstance(bid_state, dict) else {}
    journal = sync_portfolio(DATA, squad, market_players, bid_state, config, now)
    config["_trading_holdings_value"]=sum(e.get("market_value") or 0 for e in journal.get("holdings",{}).values() if e.get("purpose")=="trading")
    # All purchase paths now share the same Base-XI and withdrawal policy.
    plan = build_trade_plan(market_players, squad, {**config, "auto_buy": False}, user_id, near_matchday, budget)
    if protect_hours>0 and until_kickoff is None:
        for item in plan["blocked"]:
            if item.get("kind")=="selling":item["reason"]="Verkäufe warten: nächster Spieltagsbeginn nicht verlässlich bekannt"
    exits = apply_exits(plan, squad, market_players, journal, config, near_matchday, now)
    checks = league_checks(squad, market_players, budget, config, live, now)
    if checks["mvp_id"]:
        # League rule requires a sale to KICKBASE, not to another manager.
        plan["actions"] = [a for a in plan["actions"] if not (a.get("player_id")==checks["mvp_id"] and a["kind"]=="accept_offer")]
        plan["blocked"].append({"player_id":checks["mvp_id"],"player":"MVP", "reason":"Bestätigten MVP an KICKBASE verkaufen; kein Managerangebot automatisch annehmen"})
    result = {
        "enabled": bool(config.get("trading_enabled")),
        "mode": "live" if live_mode else "observe",
        "status": "Aktiv" if live_mode else "Testmodus",
        "actions": [],
        "planned": [],
        "blocked": list(plan["blocked"]),
        "best_lineup": plan["lineup"],
        "target_lineup": plan.get("target_lineup", plan["lineup"]),
        "upgrades": plan.get("upgrades", []),
        "portfolio": plan.get("portfolio", {}),
        "exits": exits,
        "league_checks": checks,
        "journal": report(journal),
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
        amount = action.get("amount")
        paid = int(journal.get("holdings", {}).get(engine_player_id(player), {}).get("cost") or pick(player, "purchasePrice", "buyPrice", "bp", "bpr", default=0) or 0)
        profit = amount - paid if paid and isinstance(amount, (int, float)) and action.get("kind") in ("accept_offer", "instant_sell") else None
        return {
            "time": stamp,
            "action": action["kind"],
            "player_id": engine_player_id(player),
            "player": engine_player_name(player),
            "reason": action.get("reason", ""),
            "amount": amount,
            "purchase_price": paid or None,
            "profit": profit,
            "purpose": action.get("purpose"),
        }

    priority = {"withdraw_bid": -1, "accept_offer": 0, "buy": 1, "instant_sell": 2, "list": 3, "adjust_price": 4}
    # Retain purchase intent across market disappearance until roster reconciliation.
    bid_state = {pid:item for pid,item in bid_state.items() if isinstance(item,dict) and now-float(item.get("time",0))<30*86400}
    bids = plan_bids(market_players, squad, config, user_id, budget, bid_state, risky_names)
    plan["actions"].extend(bids["actions"])
    result["blocked"].extend(bids["blocked"])
    result["scouting"] = bids["ratings"]
    result["combination"] = bids.get("combination")
    result["capital"] = bids.get("capital", {"budget":budget,"notice":"Noch kein vollständiger Kapitalplan"})
    open_bids=[{"player":engine_player_name(p),"player_id":engine_player_id(p),"amount":own_offer(p,user_id)["amount"]}
               for p in market_players if own_offer(p,user_id)]
    exposure=sum(x["amount"] for x in open_bids)
    reserve=max(0,int(config.get("minimum_cash",1_000_000)))
    result["capital"].update(budget=budget,open_bids=exposure,open_bid_details=open_bids,reserve=reserve,
                             free=max(0,budget-reserve-exposure) if budget is not None else None)
    if bids.get("combination"):
        result["target_lineup"] = bids["combination"]["target"]
        result["upgrades"] = [{"player_id":pid} for pid in bids["combination"]["ids"]]
        shadow_config = {**config, "minimum_cash":int(config.get("trial_minimum_cash",2_000_000))}
        shadow_ratings = {pid:{**r,"eligible":r.get("eligible",False) and (s11_score(next((p for p in market_players if engine_player_id(p)==pid),{})) or 0)>=int(config.get("trial_min_s11",4))} for pid,r in bids["ratings"].items()}
        alternative = choose_combination(market_players,squad,shadow_ratings,budget,shadow_config,
                                         reserved=result["capital"].get("open_bids",0))
        result["trial"] = shadow_trial(DATA,{"Aktive Regeln":bids["combination"],"Proberegeln":alternative},market_players+squad,shadow_config,now)
        result["trial"]["comparison"] = alternative
    result["replacements"] = []
    for p in squad:
        pid=engine_player_id(p)
        remaining=[x for x in squad if engine_player_id(x)!=pid]
        alternatives=[x for x in market_players if x.get("pos",x.get("position"))==p.get("pos",p.get("position"))
                      and bids["ratings"].get(engine_player_id(x),{}).get("eligible") and expected(x)>=expected(p)]
        result["replacements"].append({"id":pid,"name":engine_player_name(p),
            "sale_floor":next((e["accept"] for e in exits if e["player_id"]==pid),None),
            "secured":projection(remaining)["complete"] and len(remaining)>=int(config.get("minimum_squad_size",11)),
            "alternatives":[{"id":engine_player_id(x),"name":engine_player_name(x),
                             "price":bids["ratings"][engine_player_id(x)]["amount"],
                             "affordable_now":budget is not None and bids["ratings"][engine_player_id(x)]["amount"]<=result["capital"].get("free",0)}
                            for x in sorted(alternatives,key=expected,reverse=True)[:3]]})
    validated = []
    priced_actions = {"accept_offer", "buy", "list", "adjust_price", "instant_sell"}
    for action in plan["actions"]:
        kind = action.get("kind")
        player = action.get("player", {})
        pid = engine_player_id(player)
        amount = action.get("amount")
        invalid_amount = kind in priced_actions and (
            isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0
        )
        offer = action.get("offer", {})
        offer_id = identity(offer.get("offerId") or offer.get("uoid") or offer.get("id") or offer.get("i") or offer.get("u"))
        if kind == "withdraw_bid":
            verified = own_offer(player, user_id)
            if not verified or verified["offer_id"] != action.get("offer_id"):
                result["blocked"].append({"player": engine_player_name(player), "reason": "Gebot gehört nicht nachweisbar dir"})
                continue
        if kind not in priority or not pid or invalid_amount or (kind == "accept_offer" and not offer_id):
            result["blocked"].append({
                "player_id": pid,
                "player": engine_player_name(player) or "Unbekannter Spieler",
                "reason": "Aktion blockiert: unvollständige oder ungültige Handelsdaten",
            })
            continue
        validated.append(action)
    selected = sorted(validated, key=lambda item: priority[item["kind"]])[:max_actions]
    result["planned"] = [compact(action) for action in selected]
    if not live_mode:
        result["status"] = f"Testmodus: {len(selected)} geplante Aktion(en)"
        return result

    for action in selected:
        player = action.get("player", {})
        pid = engine_player_id(player)
        try:
            if action["kind"] == "withdraw_bid":
                offer_id = quote(action["offer_id"], safe="")
                client.write("DELETE", f"/v4/leagues/{quote(str(league_id), safe='')}/market/{quote(pid, safe='')}/offers/{offer_id}")
            elif action["kind"] == "accept_offer":
                offer = action["offer"]
                offer_id = identity(offer.get("offerId") or offer.get("uoid") or offer.get("id") or offer.get("i") or offer.get("u"))
                client.write("DELETE", f"/v4/leagues/{league_id}/market/{pid}/offers/{quote(offer_id, safe='')}/accept")
            elif action["kind"] == "instant_sell":
                client.write("DELETE", f"/v4/leagues/{league_id}/market/{pid}/sell")
            elif action["kind"] in ("list", "adjust_price"):
                # Observed compact fields plus documented aliases. Both operations
                # set a transfer price; neither accepts an offer or sells a player.
                client.write("POST", f"/v4/leagues/{league_id}/market/", {
                    "pi": pid, "prc": action["amount"], "playerId": pid, "price": action["amount"]})
            elif action["kind"] == "buy":
                client.write("POST", f"/v4/leagues/{league_id}/market/{pid}/offers", {"price": action["amount"]})
            entry = {**compact(action), "ok": True}
            if action["kind"] == "buy":
                bid_state[pid] = {"amount": action["amount"], "time": time.time(), "purpose": action.get("purpose"),
                                  "reason":action.get("reason"),"ceiling":bids["ratings"].get(pid,{}).get("ceiling")}
            elif action["kind"] == "withdraw_bid":
                bid_state.pop(pid, None)
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            entry = {**compact(action), "ok": False, "error": str(exc)[:240]}
        result["actions"].append(entry)
        trade_log(entry)
    save_json(bid_state_path, bid_state)
    record_receipts(DATA,result["actions"],now)
    result["status"] = f"{sum(1 for item in result['actions'] if item['ok'])} Aktion(en) ausgeführt"
    return result


def run_once(safe_check=False):
    email = keyring.get_password(APP, "email")
    password = keyring.get_password(APP, "password")
    if not email or not password:
        raise RuntimeError("Keine lokalen Zugangsdaten gefunden. Bitte INSTALLIEREN.bat erneut starten.")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if safe_check:
        # Installation checks connectivity and data reads only. Never trade here,
        # even when an existing configuration is already in live mode.
        config["trading_enabled"] = False
        config["mode"] = "observe"
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
    # Budget comes from the matched user's league selection, never lineup.b
    # (which is a team-value delta, not the account balance).
    selection = client.get_optional("/v4/leagues/selection")
    selected_league = next((x for x in list_from(selection.get("data",{}))
                           if isinstance(x,dict) and str(pick(x,"id","i","leagueId","li"))==str(league_id)),None)
    config["_budget"] = number(selected_league.get("b")) if selected_league else None
    market_raw = client.get(f"/v4/leagues/{league_id}/market", f"/v4/league/{league_id}/market")
    players = list_from(market_raw)
    extra = {
        "me": client.get_optional(f"/v4/leagues/{league_id}/me", f"/v4/league/{league_id}/me"),
        "info": client.get_optional(f"/v4/leagues/{league_id}/info", f"/v4/league/{league_id}/info"),
        "lineup": client.get_optional(f"/v4/leagues/{league_id}/lineup/overview"),
        "squad": client.get_optional(f"/v4/leagues/{league_id}/squad"),
        "overview": client.get_optional(f"/v4/leagues/{league_id}/overview"),
        "users": client.get_optional(f"/v4/leagues/{league_id}/users", f"/v4/league/{league_id}/users"),
        "stats": client.get_optional(f"/v4/leagues/{league_id}/stats", f"/v4/league/{league_id}/stats"),
        "feed": client.get_optional(f"/v4/leagues/{league_id}/feed?start=0", f"/v4/league/{league_id}/feed?start=0")
    }
    actual_lineup = extra["lineup"].get("data",{})
    config["_submitted_lineup"] = actual_lineup.get("lp") if isinstance(actual_lineup,dict) and extra["lineup"].get("ok") else None
    limits = extra["overview"].get("data",{})
    if isinstance(limits,dict):
        for field, key in (("mpst","maximum_per_club"),("mppu","maximum_squad_size")):
            cap = number(limits.get(field))
            if cap is not None and cap > 0:config[key]=min(int(cap),int(config.get(key,3 if field=="mpst" else 18)))
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
    user_id = login_user_id(login)
    squad_players = normalized_squad(extra, players, user_id)
    squad_players = hydrate_squad_details(client, league_id, squad_players, config)
    ligainsider = fetch_ligainsider(squad_players + players, config)
    players = enrich_s11(players, ligainsider)
    squad_players = enrich_s11(squad_players, ligainsider)
    kickbest = fetch_kickbest(squad_players + players, config)
    players = enrich_performance(players, kickbest)
    squad_players = enrich_performance(squad_players, kickbest)
    base_xi = fetch_base_xi(DATA, config)
    base_xi = fetch_base_xi_forms(base_xi, players + squad_players, DATA, config)
    players = enrich_base_xi(players, base_xi)
    squad_players = enrich_base_xi(squad_players, base_xi)
    combined = enrich_recent(client,league_id,squad_players+players,DATA)
    squad_players,players = combined[:len(squad_players)],combined[len(squad_players):]
    squad_players = purchase_details(client,league_id,squad_players,user_id,DATA)
    now=time.time()
    players=annotate(players,base_xi,now,config)
    squad_players=annotate(squad_players,base_xi,now,config)
    config["_enriched_squad"] = squad_players
    squad_payload=extra["squad"].get("data",{})
    config["_roster_reliable"] = extra["squad"].get("ok",False) and isinstance(squad_payload,dict) and isinstance(squad_payload.get("it"),list)
    recommended_lineup = best_lineup(squad_players)
    watched_players = [{"name": name} for name in config.get("watchlist_names", []) if str(name).strip()]
    news, new_news = news_monitor(squad_players + players + watched_players, config)
    trading = run_trading(client, league_id, players, extra, config, live, user_id, news.get("items", []))
    events = []
    labels = {"withdraw_bid": "Gebot zurückgezogen", "buy": "Kaufgebot abgegeben",
              "list": "Auf den Markt gestellt", "adjust_price": "Verkaufspreis angepasst",
              "accept_offer": "Angebot angenommen", "instant_sell": "Sofortverkauf"}
    for item in trading.get("actions", []):
        status = labels.get(item["action"], item["action"]) if item.get("ok") else "Aktion fehlgeschlagen"
        text = f"{status}: {item['player']} – {int(item.get('amount') or 0):,} € · {item['reason']}"
        if item.get("profit") is not None and item.get("ok"):
            text += f" · Gewinn/Verlust {int(item['profit']):,} €"
        if item.get("error"):
            text += " · " + item["error"]
        event_id="trade:" + item["time"] + item["action"] + item["player_id"] if item.get("ok") else "failed:"+item["action"]+item["player_id"]+str(item.get("error",""))
        events.append({"id": event_id, "text": text,"category":"Bestätigte Aktionen" if item.get("ok") else "Fehlgeschlagene Aktionen"})
    for item in trading.get("blocked", []):
        if item.get("player") not in ("Budget","Konto","MVP","Winterreset"):
            continue
        text = f"Blockiert: {item.get('player', 'Handel')} · {item['reason']}"
        events.append({"id": text, "text": text})
    for item in new_news:
        events.append({"id": "news:" + item["id"],
                       "text": f"Risiko-Hinweis: {item['player']} · {item['title']}\n{item['url']}"})
    for check in trading.get("league_checks",{}).get("checks",[]):
        events.append({"id":"league:"+check,"text":check,"category":"Wichtige Hinweise"})
    if not base_xi.get("available"):
        events.append({"id":"source:base-xi","text":"Base-XI aktuell nicht verfügbar; neue Käufe warten.","category":"Wichtige Hinweise"})
    config["_digest_summary"]={"capital":trading.get("capital",{}),
                               "results":trading.get("journal",{})}
    notification = ({"sent": False, "reason": "Installationstest ohne E-Mail"} if safe_check else
                    hourly_digest(DATA, config, events, send_email))
    snapshot = {"updated_at": stamp, "league": config["league_name"], "market": market_raw}
    (DATA / "letzter_markt.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {
        **snapshot,
        "league_id": league_id,
        "account_budget": config["_budget"],
        "league_meta": league,
        "user_id": user_id,
        "squad": squad_players,
        "players": players,
        "best_lineup": recommended_lineup,
        "ligainsider": ligainsider,
        "kickbest": kickbest,
        "base_xi": {key: value for key, value in base_xi.items() if key != "players"},
        "version": "2026.09.15-portfolio-2",
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
    parser.add_argument("--safe-check", action="store_true")
    args = parser.parse_args()
    if args.loop:
        while True:
            try:
                run_once()
            except Exception as exc:
                logging.exception("Aktualisierung fehlgeschlagen")
                print(f"Fehler: {exc}")
            config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            time.sleep(max(5, int(config.get("poll_minutes", 5))) * 60)
    else:
        run_once(safe_check=args.safe_check)


if __name__ == "__main__":
    main()

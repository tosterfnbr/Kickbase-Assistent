"""Pure decision logic for S11, best XI, selling and pricing.

No network or KICKBASE writes live here, so every rule can be unit-tested.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

FORMATIONS = ((3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2), (4, 5, 1), (5, 3, 2), (5, 4, 1))
POSITION_MINIMUM = {1: 1, 2: 3, 3: 3, 4: 1}


def pick(obj, *keys, default=None):
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            return obj[key]
    return default


def player_id(player):
    return str(pick(player, "id", "i", "playerId", "pi", default=""))


def player_name(player):
    return " ".join(str(v) for v in (
        pick(player, "firstName", "fn", default=""),
        pick(player, "lastName", "n", "name", default=""),
    ) if v).strip()


def normalize_name(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _number(player, *keys):
    value = pick(player, *keys, default=None)
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def kickbase_s11(player):
    """Return 1..5 or None. Zero/missing is unknown, never a negative signal."""
    value = _number(player, "prob", "lineupProbability", "startingProbability")
    if value is None or value <= 0:
        return None
    if value <= 1:  # tolerate APIs returning a 0..1 probability
        value *= 5
    return max(1, min(5, int(round(value))))


def enrich_s11(players, ligainsider):
    """Merge sources without overwriting raw KICKBASE data."""
    forecasts = ligainsider.get("players", {}) if isinstance(ligainsider, dict) else {}
    output = []
    for original in players:
        player = dict(original)
        key = normalize_name(player_name(player))
        li = forecasts.get(key, {}) if key else {}
        kb = kickbase_s11(player)
        li_score = li.get("score") if isinstance(li, dict) else None
        if isinstance(li_score, (int, float)) and 1 <= li_score <= 5:
            # A confirmed LigaInsider forecast has priority; retain KB for audit.
            score, source = int(li_score), "LigaInsider"
        elif kb is not None:
            score, source = kb, "KICKBASE"
        else:
            score, source = None, "unbekannt"
        player["s11"] = {
            "score": score,
            "source": source,
            "kickbase": kb,
            "ligainsider": li_score,
            "status": li.get("status") if isinstance(li, dict) else None,
            "checked_at": ligainsider.get("checked_at") if isinstance(ligainsider, dict) else None,
        }
        output.append(player)
    return output


def s11_score(player):
    nested = player.get("s11") if isinstance(player, dict) else None
    if isinstance(nested, dict):
        score = nested.get("score")
        if isinstance(score, (int, float)) and 1 <= score <= 5:
            return int(score)
        return None
    return kickbase_s11(player)


def _quality(player):
    s11 = s11_score(player)
    points = _number(player, "averagePoints", "avgPoints", "ap", "points", "p")
    value = _number(player, "marketValue", "mv") or 0
    trend = int(_number(player, "marketValueTrend", "mvt") or 0)
    # S11 dominates. Unknown stays selectable only when a position cannot be filled otherwise.
    return (s11 if s11 is not None else -1) * 1_000_000 + (points or 0) * 10_000 + (1 if trend == 2 else 0) * 1_000 + math.log10(max(value, 1))


def best_lineup(players):
    """Return the highest-scoring valid XI across common Bundesliga formations."""
    usable = [p for p in players if player_id(p) and int(_number(p, "position", "pos") or 0) in POSITION_MINIMUM]
    by_pos = {pos: sorted((p for p in usable if int(_number(p, "position", "pos") or 0) == pos), key=_quality, reverse=True) for pos in POSITION_MINIMUM}
    best = None
    for defenders, midfielders, forwards in FORMATIONS:
        needs = {1: 1, 2: defenders, 3: midfielders, 4: forwards}
        if any(len(by_pos[pos]) < count for pos, count in needs.items()):
            continue
        lineup = [p for pos in (1, 2, 3, 4) for p in by_pos[pos][:needs[pos]]]
        score = sum(_quality(p) for p in lineup)
        candidate = {"formation": f"{defenders}-{midfielders}-{forwards}", "players": lineup, "score": score}
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    if best is None:
        fallback = sorted(usable, key=_quality, reverse=True)[:11]
        best = {"formation": "unvollständig", "players": fallback, "score": sum(_quality(p) for p in fallback)}
    ids = {player_id(p) for p in best["players"]}
    best["bench"] = sorted((p for p in usable if player_id(p) not in ids), key=_quality, reverse=True)
    best["complete"] = len(best["players"]) == 11 and best["formation"] != "unvollständig"
    return best


def price_limits(player, config):
    """Dynamic list and acceptance prices, bounded by configured percentages."""
    mv = int(_number(player, "marketValue", "mv") or 0)
    if mv <= 0:
        return {"asking": 0, "accept": 0}
    score = s11_score(player)
    trend = int(_number(player, "marketValueTrend", "mvt") or 0)
    base_markup = float(config.get("asking_price_percent", 2))
    if trend == 2:
        base_markup += float(config.get("rising_price_bonus_percent", 3))
    elif trend == 1:
        base_markup -= float(config.get("falling_price_discount_percent", 2))
    if score is not None and score >= 4:
        base_markup += float(config.get("safe_s11_price_bonus_percent", 2))
    markup = max(-10, min(30, base_markup))
    minimum_offer = max(70, min(120, float(config.get("minimum_offer_percent", 98))))
    return {
        "asking": int(round(mv * (1 + markup / 100) / 1000) * 1000),
        "accept": int(round(mv * minimum_offer / 100 / 1000) * 1000),
    }


def selling_candidates(squad, config, protected_ids=()):
    lineup = best_lineup(squad)
    protected = set(map(str, protected_ids)) | {player_id(p) for p in lineup["players"]}
    counts = Counter(int(_number(p, "position", "pos") or 0) for p in squad)
    candidates = []
    min_s11 = int(config.get("minimum_starting_probability", 3))
    for player in squad:
        pid = player_id(player)
        pos = int(_number(player, "position", "pos") or 0)
        score = s11_score(player)
        trend = int(_number(player, "marketValueTrend", "mvt") or 0)
        if pid in protected or counts[pos] <= POSITION_MINIMUM.get(pos, 1):
            continue
        # Unknown S11 is never an automatic sell reason.
        if score is None:
            continue
        reasons = []
        severity = 0
        if score < min_s11:
            reasons.append(f"S11 {score}/5 unter Grenze")
            severity += 2
        if trend == 1:
            reasons.append("Marktwert fällt")
            severity += 1
        if not reasons:
            continue
        limits = price_limits(player, config)
        candidates.append({
            "player": player,
            "player_id": pid,
            "severity": severity,
            "reason": ", ".join(reasons),
            "method": "instant_sell" if severity >= 3 and config.get("auto_instant_sell", True) else "list",
            **limits,
        })
    return sorted(candidates, key=lambda item: (-item["severity"], _quality(item["player"])))


def build_trade_plan(market_players, squad, config, user_id="", near_matchday=False):
    """Create deterministic actions in both observe and live mode."""
    own_id = str(user_id or config.get("user_id", ""))
    actions, blocked = [], []
    own_listings = {}
    for player in market_players:
        if own_id and str(pick(player, "userId", "ui", "u", default="")) == own_id:
            own_listings[player_id(player)] = player
            limits = price_limits(player, config)
            offers = pick(player, "offers", "ofs", default=[]) or []
            priced = [(int(_number(o, "price", "prc", "p") or 0), o) for o in offers]
            best_offer = max(priced, default=(0, None), key=lambda item: item[0])
            if config.get("auto_accept_offers", True) and best_offer[1] and best_offer[0] >= limits["accept"]:
                actions.append({"kind": "accept_offer", "player": player, "player_id": player_id(player), "amount": best_offer[0], "offer": best_offer[1], "reason": "Bestes Angebot erreicht die Verkaufsgrenze"})
            else:
                current = int(_number(player, "price", "prc", "p") or 0)
                if config.get("auto_adjust_listings", True) and limits["asking"] and abs(current - limits["asking"]) >= 10_000:
                    actions.append({"kind": "adjust_price", "player": player, "player_id": player_id(player), "amount": limits["asking"], "reason": "Dynamischer Zielpreis aus Marktwert, Trend und S11"})
    if near_matchday:
        blocked.append({"kind": "selling", "reason": "Verkäufe innerhalb des Spieltag-Schutzfensters blockiert"})
    else:
        protected = config.get("protected_players", [])
        for item in selling_candidates(squad, config, protected):
            if item["player_id"] in own_listings:
                continue
            actions.append({"kind": item["method"], **item})
    return {"lineup": best_lineup(squad), "actions": actions, "blocked": blocked}

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
    performance = player.get("performance", {}) if isinstance(player, dict) else {}
    points = performance.get("average_points")
    if not isinstance(points, (int, float)):
        points = _number(player, "averagePoints", "avgPoints", "ap", "points", "p")
    ppm = performance.get("points_per_million")
    if not isinstance(ppm, (int, float)):
        ppm = 0
    value = _number(player, "marketValue", "mv") or 0
    trend = int(_number(player, "marketValueTrend", "mvt") or 0)
    # S11 dominates, followed by recent point output and value for money.
    return (s11 if s11 is not None else -1) * 1_000_000 + (points or 0) * 10_000 + min(ppm, 100) * 500 + (1 if trend == 2 else 0) * 1_000 + math.log10(max(value, 1))


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


def price_limits(player, config, is_core=False):
    """Calculate profitable list/accept limits from value, trend, S11 and buy price."""
    mv = int(_number(player, "marketValue", "mv") or 0)
    if mv <= 0:
        return {"asking": 0, "accept": 0, "basis": 0}
    paid = int(_number(player, "purchasePrice", "buyPrice", "bp", "bpr") or 0)
    basis = max(mv, paid)
    score = s11_score(player)
    trend = int(_number(player, "marketValueTrend", "mvt") or 0)
    markup = float(config.get("asking_price_percent", 2))
    if trend == 2:
        markup += float(config.get("rising_price_bonus_percent", 3))
    elif trend == 1:
        markup -= float(config.get("falling_price_discount_percent", 2))
    if score is not None and score >= 4:
        markup += float(config.get("safe_s11_price_bonus_percent", 2))
    if is_core:
        markup += float(config.get("star_listing_bonus_percent", 8))
    markup = max(-10, min(50, markup))
    minimum_offer = max(70, min(150, float(config.get("minimum_offer_percent", 98))))
    profit_floor = paid * (1 + float(config.get("target_profit_percent", 4)) / 100) if paid else 0
    core_floor = basis * (1 + float(config.get("star_sale_profit_percent", 10)) / 100) if is_core else 0
    return {
        "asking": int(round(basis * (1 + markup / 100) / 1000) * 1000),
        "accept": int(round(max(mv * minimum_offer / 100, profit_floor, core_floor) / 1000) * 1000),
        "basis": basis,
    }


def _position(player):
    return int(_number(player, "position", "pos") or 0)


def affordable_upgrades(squad, market_players, budget, config, user_id=""):
    """Plan point upgrades greedily while preserving cash and a valid XI."""
    lineup = best_lineup(squad)
    selected = list(lineup["players"])
    cash = max(0, int(budget or 0) - int(config.get("minimum_cash", 1_000_000)))
    own_id = str(user_id or config.get("user_id", ""))
    min_s11 = int(config.get("minimum_starting_probability", 3))
    proposals = []
    candidates = []
    for candidate in market_players:
        if own_id and str(pick(candidate, "userId", "ui", "u", default="")) == own_id:
            continue
        score = s11_score(candidate)
        price = int(_number(candidate, "price", "prc", "marketValue", "mv") or 0)
        pos = _position(candidate)
        if score is None or score < min_s11 or price <= 0 or pos not in POSITION_MINIMUM:
            continue
        incumbents = [p for p in selected if _position(p) == pos]
        if not incumbents:
            continue
        weakest = min(incumbents, key=_quality)
        gain = _quality(candidate) - _quality(weakest)
        if gain > 0:
            candidates.append((gain / max(price, 1), gain, price, candidate, weakest))
    used_in, used_out = set(), set()
    for _, gain, price, candidate, weakest in sorted(candidates, reverse=True, key=lambda row: (row[0], row[1])):
        cid, wid = player_id(candidate), player_id(weakest)
        if cid in used_in or wid in used_out or price > cash:
            continue
        proposals.append({
            "kind": "buy",
            "player": candidate,
            "player_id": cid,
            "replace_player_id": wid,
            "replace_player": weakest,
            "amount": price,
            "quality_gain": gain,
            "reason": f"Startelf-Upgrade auf Position {_position(candidate)}; S11 {s11_score(candidate)}/5, Ø-Punkte {candidate.get('performance', {}).get('average_points') if isinstance(candidate.get('performance'), dict) else 'unbekannt'}, Preis-Leistung geprüft",
        })
        cash -= price
        used_in.add(cid)
        used_out.add(wid)
    return {"current_lineup": lineup, "buys": proposals, "remaining_cash": cash}


def selling_candidates(squad, config, protected_ids=()):
    lineup = best_lineup(squad)
    core_ids = {player_id(p) for p in lineup["players"]}
    manual = set(map(str, protected_ids))
    counts = Counter(_position(p) for p in squad)
    candidates = []
    min_s11 = int(config.get("minimum_starting_probability", 3))
    portfolio = bool(config.get("portfolio_mode", True))
    list_all = bool(config.get("list_all_players", True))
    for player in squad:
        pid, pos = player_id(player), _position(player)
        if pid in manual:
            continue
        score = s11_score(player)
        trend = int(_number(player, "marketValueTrend", "mvt") or 0)
        is_core = pid in core_ids
        limits = price_limits(player, config, is_core=is_core)
        if list_all:
            candidates.append({
                "player": player, "player_id": pid, "severity": 0, "is_core": is_core,
                "reason": "Kapitalangebot testen" + ("; aktuell beste Elf" if is_core else "; Kaderreserve"),
                "method": "list", **limits,
            })
            continue
        if is_core and not portfolio:
            continue
        if counts[pos] <= POSITION_MINIMUM.get(pos, 1) or score is None:
            continue
        reasons, severity = [], 0
        if score < min_s11:
            reasons.append(f"S11 {score}/5 unter Grenze")
            severity += 2
        if trend == 1:
            reasons.append("Marktwert fällt")
            severity += 1
        if reasons:
            candidates.append({
                "player": player, "player_id": pid, "severity": severity, "is_core": is_core,
                "reason": ", ".join(reasons),
                "method": "instant_sell" if severity >= 3 and config.get("auto_instant_sell", True) and not is_core else "list",
                **limits,
            })
    return sorted(candidates, key=lambda item: (item["is_core"], -item["severity"], _quality(item["player"])))


def build_trade_plan(market_players, squad, config, user_id="", near_matchday=False, budget=0):
    """List the portfolio, take profitable offers and plan affordable XI upgrades."""
    own_id = str(user_id or config.get("user_id", ""))
    lineup = best_lineup(squad)
    core_ids = {player_id(p) for p in lineup["players"]}
    position_counts = Counter(_position(p) for p in squad)
    upgrade_plan = affordable_upgrades(squad, market_players, budget, config, user_id)
    replacement_for = {item["replace_player_id"]: item for item in upgrade_plan["buys"]}
    actions, blocked, own_listings = [], [], {}

    for player in market_players:
        if own_id and str(pick(player, "userId", "ui", "u", default="")) == own_id:
            pid = player_id(player)
            own_listings[pid] = player
            is_core = pid in core_ids
            limits = price_limits(player, config, is_core=is_core)
            offers = pick(player, "offers", "ofs", default=[]) or []
            priced = [(int(_number(o, "price", "prc", "p") or 0), o) for o in offers]
            best_offer = max(priced, default=(0, None), key=lambda item: item[0])
            has_depth = position_counts[_position(player)] > POSITION_MINIMUM.get(_position(player), 1)
            replacement_ready = pid in replacement_for
            sale_safe = not is_core or has_depth or replacement_ready
            if config.get("auto_accept_offers", True) and best_offer[1] and best_offer[0] >= limits["accept"] and sale_safe and not near_matchday:
                actions.append({
                    "kind": "accept_offer", "player": player, "player_id": pid,
                    "amount": best_offer[0], "offer": best_offer[1],
                    "reason": "Gewinnziel erreicht" + (" und Ersatz/Positionsreserve vorhanden" if is_core else ""),
                })
            elif best_offer[1] and best_offer[0] >= limits["accept"] and not sale_safe:
                blocked.append({"player_id": pid, "player": player_name(player), "reason": "Gutes Angebot blockiert: noch kein sicherer Ersatz"})
            else:
                current = int(_number(player, "price", "prc", "p") or 0)
                if config.get("auto_adjust_listings", True) and limits["asking"] and abs(current - limits["asking"]) >= 10_000:
                    actions.append({"kind": "adjust_price", "player": player, "player_id": pid, "amount": limits["asking"], "reason": "Gewinnorientierter Zielpreis aus Kaufpreis, Marktwert, Trend und S11"})

    if near_matchday:
        blocked.append({"kind": "selling", "reason": "Annahmen und neue Verkäufe im Spieltag-Schutzfenster blockiert"})
    else:
        for item in selling_candidates(squad, config, config.get("protected_players", [])):
            if item["player_id"] not in own_listings:
                actions.append({"kind": item["method"], **item})

    actions.extend(upgrade_plan["buys"])
    return {
        "lineup": lineup,
        "target_lineup": lineup,
        "upgrades": upgrade_plan["buys"],
        "actions": actions,
        "blocked": blocked,
        "portfolio": {
            "listed_or_planned": len(own_listings) + sum(a["kind"] == "list" for a in actions),
            "squad_size": len(squad),
            "core_players": len(core_ids),
            "remaining_upgrade_cash": upgrade_plan["remaining_cash"],
        },
    }

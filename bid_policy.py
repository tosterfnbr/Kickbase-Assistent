"""A single policy for new purchases and withdrawal of verified own bids."""
from base_xi import number
from decision_engine import best_lineup, player_id, player_name, s11_score


def identity(value):
    if isinstance(value, dict):
        value = value.get("id") or value.get("i")
    return str(value) if value not in (None, "", "0", 0, False) else ""


def owner_id(player):
    return identity(player.get("userId") or player.get("ui") or player.get("u"))


def login_user_id(login):
    return identity(login.get("user") or login.get("u")) or identity(
        login.get("userId") or login.get("ui") or login.get("id") or login.get("i")
    )


def own_offer(player, user_id):
    """Use live bidder identity, never the mere existence of an offers array.

    KICKBASE's uoid/uop mirror identifies the bidder and price. The own bidder
    ID is also the withdrawal path ID in this API. Nested offers are accepted
    only with matching bidder identity (never incoming offers on own listings).
    """
    uid = identity(user_id)
    if not uid or owner_id(player) == uid:
        return None
    if identity(player.get("uoid")) == uid and (number(player.get("uop")) or 0) > 0:
        return {"offer_id": uid, "amount": int(number(player["uop"]))}
    for offer in player.get("ofs") or player.get("offers") or []:
        if not isinstance(offer, dict):
            continue
        bidder = identity(offer.get("u") or offer.get("uoid") or offer.get("userId"))
        amount = number(offer.get("uop", offer.get("price", offer.get("prc"))))
        if bidder == uid and amount is not None and amount > 0:
            return {"offer_id": identity(offer.get("offerId")) or bidder, "amount": int(amount)}
    return None


def assess(player, config, purpose=None):
    bx = player.get("base_xi") or {}
    mv = number(player.get("marketValue")) or number(player.get("mv"))
    score = s11_score(player)
    minimum = int(config.get("minimum_starting_probability", 3))
    reason, conclusive = None, True
    status = number(player.get("status", player.get("st")))
    if status is not None and status != 0:
        reason = "KICKBASE meldet eingeschränkte Verfügbarkeit"
    elif score is not None and score < minimum:
        reason = "S11-Prognose unter der eingestellten Grenze"
    elif not bx.get("available"):
        reason, conclusive = "Base-XI-Daten fehlen oder sind veraltet", False
    elif bx.get("status") is not None and bx["status"] != 0:
        reason = "Base-XI meldet Verletzung, Sperre oder eingeschränkte Verfügbarkeit"
    elif not mv or mv <= 0:
        reason, conclusive = "Aktueller Marktwert fehlt", False
    if reason:
        return {"eligible": False, "reason": reason, "conclusive": conclusive, "purpose": purpose}

    price = number(player.get("price", player.get("prc"))) or mv
    bid = int(max(mv, price))  # league rule: never buy below market value
    ceiling = int(mv * (1 + max(0, min(30, float(config.get("maximum_overpay_percent", 8)))) / 100))
    fv = bx.get("fair_value")
    if fv and fv > 0:
        ceiling = min(ceiling, int(fv))
    if bid > ceiling:
        return {"eligible": False, "reason": "Preis über Aufpreisgrenze oder Base-XI Fair Value",
                "conclusive": True, "purpose": purpose, "ceiling": ceiling}

    # Historical starts and season average minutes are not next-match S11 or
    # per-match minutes. Keep those criteria explicitly named in explanations.
    regular = (score is not None and score >= minimum
               and (bx.get("matches") or 0) >= 2
               and (bx.get("average_minutes") or 0) >= 45
               and (bx.get("average_points") or 0) >= 50)
    delta = bx.get("trend_24h")
    forecast = bx.get("ki_trend")
    gain = (delta or 0) * 2 - (bid - mv)
    trader = (config.get("trading_buys_enabled", True)
              and delta is not None and delta > 0
              and forecast is not None and forecast >= 0
              and bx.get("gamble") != 1
              and bid <= int(config.get("max_trading_player_price", 3_000_000))
              and gain >= int(config.get("minimum_trading_gain", 100_000)))
    if purpose == "startelf":
        eligible = regular
    elif purpose == "trading":
        eligible = trader
    else:
        purpose = "startelf" if regular else "trading"
        eligible = regular or trader
    reason = (
        "Startelf-Kandidat: S11, mindestens 2 Saisoneinsätze, Ø 45 Minuten und Ø 50 Punkte"
        if purpose == "startelf" else
        "Trading: positiver 24h-Trend und KI-Trend; begrenzter Einsatz, keine Gewinnzusage"
    ) if eligible else (
        "Startelf-Kriterien für Einsätze, Minuten oder Punkte nicht mehr erfüllt"
        if purpose == "startelf" else "Trading-Kriterien für Trend, Preis oder Gewinnpotenzial nicht erfüllt"
    )
    needed = ("matches", "average_minutes", "average_points") if purpose == "startelf" else ("trend_24h", "ki_trend")
    conclusive = eligible or all(bx.get(key) is not None for key in needed)
    return {"eligible": bool(eligible), "conclusive": conclusive, "reason": reason,
            "purpose": purpose, "amount": bid, "ceiling": ceiling,
            "score": (bx.get("average_points") or 0) if purpose == "startelf" else gain / bid}


def plan_bids(players, squad, config, user_id, budget, saved=None, risky_names=()):
    """Withdraw adverse own offers first; reserve every outstanding bid as cash.

    Do not count expected sales or planned withdrawals as money already received.
    Manual own bids are also managed if auto_withdraw_bids is enabled.
    """
    saved = saved or {}
    actions, blocked, ratings, verified = [], [], {}, {}
    uid = identity(user_id)
    own_ids = {player_id(p) for p in squad}
    if not uid:
        return {"actions": [], "blocked": [{"player": "Konto", "reason": "Eigene Nutzer-ID fehlt"}], "ratings": {}}
    current_lineup = best_lineup(squad)
    for p in players:
        pid = player_id(p)
        if not pid or pid in own_ids or owner_id(p) == uid:
            continue
        old = own_offer(p, uid)
        if old:
            verified[pid] = (p, old)
        stored = saved.get(pid, {}) if isinstance(saved.get(pid, {}), dict) else {}
        rating = assess(p, config, stored.get("purpose") if old else None)
        name = player_name(p).casefold()
        if name in risky_names or (name and name.split()[-1] in risky_names):
            rating = {**rating, "eligible": False, "conclusive": True, "reason": "Aktueller Risiko-Hinweis"}
        if old and old["amount"] > rating.get("ceiling", float("inf")):
            rating = {**rating, "eligible": False, "conclusive": True, "reason": "Eigenes Gebot über aktueller Preisgrenze"}
        if rating.get("eligible") and rating.get("purpose") == "startelf":
            pos = p.get("position", p.get("pos"))
            incumbents = [x for x in current_lineup["players"] if x.get("position", x.get("pos")) == pos]
            # An incomplete position is a useful purchase too (e.g. no striker).
            if incumbents:
                weakest = min(incumbents, key=lambda x: (x.get("performance") or {}).get("average_points") or x.get("ap") or 0)
                points = (weakest.get("performance") or {}).get("average_points") or weakest.get("ap") or 0
                if rating["score"] <= points:
                    rating = {**rating, "eligible": False, "conclusive": True, "reason": "Keine Punkteverbesserung auf dieser Position"}
                else:
                    rating["replace_player_id"] = player_id(weakest)
        ratings[pid] = rating
        if not rating["eligible"]:
            blocked.append({"player_id": pid, "player": player_name(p), "reason": rating["reason"]})
            if old and rating["conclusive"] and config.get("auto_withdraw_bids", True):
                actions.append({"kind": "withdraw_bid", "player": p, "player_id": pid,
                                **old, "purpose": rating.get("purpose"), "reason": rating["reason"]})

    cash = number(budget)
    if cash is None:
        blocked.append({"player": "Budget", "reason": "Keine neuen Käufe ohne verlässlichen Kontostand"})
        return {"actions": actions, "blocked": blocked, "ratings": ratings}
    cash = max(0, cash - max(0, int(config.get("minimum_cash", 1_000_000))))
    exposure = sum(offer["amount"] for _, offer in verified.values())
    cancelling = {a["player_id"] for a in actions}
    kept_cost = sum(o["amount"] for pid, (_, o) in verified.items() if pid not in cancelling)
    if config.get("auto_withdraw_bids", True) and kept_cost > cash:
        for pid, (p, old) in sorted(verified.items(), key=lambda item: ratings[item[0]].get("score", 0)):
            if pid in cancelling:
                continue
            actions.append({"kind": "withdraw_bid", "player": p, "player_id": pid, **old,
                            "reason": "Offene Gebote überschreiten Budget inklusive Reserve"})
            kept_cost -= old["amount"]
            if kept_cost <= cash:
                break
    # Wait for successful withdrawals and a fresh market snapshot before rebidding.
    if actions or not config.get("auto_buy", True):
        return {"actions": actions, "blocked": blocked, "ratings": ratings}
    available = max(0, cash - exposure)
    trade_limit = min(int(config.get("max_trading_total", 5_000_000)), cash * 0.2)
    trade_spend = sum(old["amount"] for pid, (_, old) in verified.items() if ratings[pid].get("purpose") == "trading")
    replaced, bought_positions = set(), set()
    pool = [p for p in players if ratings.get(player_id(p), {}).get("eligible")]
    pool.sort(key=lambda p: (ratings[player_id(p)]["purpose"] != "startelf", -ratings[player_id(p)]["score"], player_id(p)))
    for p in pool:
        pid = player_id(p)
        r = ratings[pid]
        old_amount = verified[pid][1]["amount"] if pid in verified else 0
        delta = max(0, r["amount"] - old_amount)
        replacement = r.get("replace_player_id")
        position = p.get("position", p.get("pos"))
        if r["purpose"] == "startelf" and (replacement in replaced or position in bought_positions):
            continue
        if delta > available or (r["purpose"] == "trading" and trade_spend + delta > trade_limit):
            continue
        expiry = number(p.get("expiry", p.get("exs")))
        if expiry is not None and expiry <= 0:
            continue
        if not config.get("continuous_bidding", True) and (expiry is None or expiry > int(config.get("bid_window_minutes", 10)) * 60):
            continue
        # The live API, not a local timer, determines whether the price changed.
        if old_amount != r["amount"]:
            actions.append({"kind": "buy", "player": p, "player_id": pid,
                            "amount": r["amount"], "purpose": r["purpose"], "reason": r["reason"]})
        available -= delta
        if r["purpose"] == "trading":
            trade_spend += delta
        else:
            replaced.add(replacement)
            bought_positions.add(position)
    return {"actions": actions, "blocked": blocked, "ratings": ratings}

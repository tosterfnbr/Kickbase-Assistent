"""A single policy for new purchases and withdrawal of verified own bids."""
from base_xi import number
from decision_engine import best_lineup, player_id, player_name, s11_score
from strategy import projection, expected, position, choose_combination, price_ceiling
from recent_data import timestamp


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
    analysis = player.get("analysis") or {}
    if analysis.get("minutes_complete"):
        regular = regular and analysis["recent_minutes"] >= 45 and (analysis.get("recent_points") or 0) >= 50
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
            "score": expected(player) if purpose == "startelf" else gain / bid,
            "facts": {"s11":score,"recent_minutes":analysis.get("recent_minutes"),
                      "recent_points":analysis.get("recent_points"),"season_points":bx.get("average_points"),
                      "trend_24h":delta,"ki_trend":forecast},
            "confidence":analysis.get("confidence","gering")}


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
                weakest = min(incumbents, key=expected)
                points = expected(weakest)
                if rating["score"] <= points:
                    bench = [x for x in current_lineup.get("bench",[]) if position(x)==position(p) and (s11_score(x) or 0)>=3]
                    if config.get("advanced_planner",True) and not bench and rating["amount"]<=int(config.get("bench_player_budget",4_000_000)):
                        rating.update(purpose="bench",reason="Bezahlbare Absicherung für diese Position")
                    else:
                        rating = {**rating, "eligible": False, "conclusive": True, "reason": "Keine Punkteverbesserung auf dieser Position"}
                else:
                    rating["replace_player_id"] = player_id(weakest)
        if config.get("advanced_planner",True) and rating.get("eligible"):
            cap,gain=price_ceiling(p,players,squad,rating["ceiling"],config)
            rating.update(ceiling=cap,expected_gain=gain)
            if rating["amount"]>cap or (old and old["amount"]>cap):
                rating.update(eligible=False,conclusive=True,reason="Preis oberhalb der individuellen Grenze unter Berücksichtigung von Alternativen")
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
    if actions:
        return {"actions": actions, "blocked": blocked, "ratings": ratings}
    if config.get("advanced_planner",True):
        result=advanced_bids(players,squad,config,uid,budget,verified,ratings,blocked)
        if not config.get("auto_buy",True):result["actions"]=[a for a in result["actions"] if a["kind"]=="withdraw_bid"]
        return result
    if not config.get("auto_buy",True):
        return {"actions": [], "blocked": blocked, "ratings": ratings}
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


def advanced_bids(players,squad,config,user_id,budget,verified,ratings,blocked):
    """Compare complete purchase baskets; withdraw before reallocating money."""
    now=float(config.get("_now",__import__("time").time()))
    reset=timestamp(config.get("winter_reset_at")) if config.get("winter_reset_enabled") else None
    if reset is not None and reset<=now:
        return {"actions":[],"ratings":ratings,"blocked":blocked+[{"player":"Winterreset","reason":"Reset-Termin erreicht; Datum und neuen Kader prüfen"}]}
    tradable=[]
    for p in players:
        pid=player_id(p)
        expiry=number(p.get("expiry",p.get("exs")))
        if expiry is not None and expiry<=0:continue
        if not config.get("continuous_bidding",True) and (expiry is None or expiry>int(config.get("bid_window_minutes",10))*60):continue
        if reset is not None and reset-now<7*86400 and projection(squad)["complete"]:
            dates=[timestamp(x.get("date")) for x in (p.get("analysis") or {}).get("opponents",[]) if timestamp(x.get("date"))]
            if not dates or min(dates)>=reset:
                blocked.append({"player_id":pid,"player":player_name(p),"reason":"Kein belegter Einsatz vor dem nahen Winterreset"})
                continue
        if ratings.get(pid,{}).get("eligible"):tradable.append(p)
    # Reserve unassessable/ineligible offers. A source outage cannot release them.
    fixed=sum(o["amount"] for pid,(_,o) in verified.items() if not ratings.get(pid,{}).get("eligible"))
    basket=choose_combination(tradable,squad,ratings,budget,config,reserved=fixed)
    chosen=set(basket["ids"])
    current=projection(squad)
    existing_roster=squad+[p for pid,(p,o) in verified.items() if ratings[pid].get("purpose") in ("startelf","bench") and ratings[pid].get("eligible")]
    existing=projection(existing_roster)
    significant=(basket["target"]["filled"]>existing["filled"] or basket["target"]["minimum_shortfall"]<existing["minimum_shortfall"] or basket["target"]["expected_points"]>=existing["expected_points"]+float(config.get("bid_switch_min_gain",10)))
    switches=[]
    if chosen and significant and config.get("auto_withdraw_bids",True) and config.get("auto_buy",True):
        for pid,(p,offer) in verified.items():
            if pid not in chosen and ratings[pid].get("eligible"):
                switches.append({"kind":"withdraw_bid","player":p,"player_id":pid,**offer,
                                 "purpose":ratings[pid].get("purpose"),"reason":"Bessere bezahlbare Kaufkombination gefunden; Budget erst nach Rücknahme neu einsetzen"})
    if switches:
        return {"actions":switches,"ratings":ratings,"blocked":blocked,"combination":basket}
    reserve=max(0,float(config.get("minimum_cash",1_000_000)))
    cash=max(0,float(budget)-reserve)
    exposure=sum(o["amount"] for p,o in verified.values())
    available=max(0,cash-exposure)
    actions=[]
    free_slots=max(0,int(config.get("maximum_squad_size",18))-len(squad)-len(verified))
    for p in tradable:
        pid=player_id(p)
        if pid not in chosen:continue
        r=ratings[pid];old=verified.get(pid,(None,{"amount":0}))[1]["amount"]
        delta=max(0,r["amount"]-old)
        if delta>available or (not old and free_slots<=0):continue
        if old!=r["amount"]:
            actions.append({"kind":"buy","player":p,"player_id":pid,"amount":r["amount"],"purpose":r["purpose"],
                            "reason":r["reason"]+"; Teil der besten gefundenen Kaufkombination"})
        available-=delta
        if not old:free_slots-=1
    # Protect funding for missing starters first; trades do not solve a vacancy.
    bench_depth=len(current["bench"])
    fraction=.2 if bench_depth>=int(config.get("bench_size",2)) else .1
    trade_limit=min(int(config.get("max_trading_total",5_000_000)),cash*fraction) if current["complete"] else 0
    if reset is not None and reset-now<float(config.get("trading_max_hold_days",7))*86400:trade_limit=0
    invested=max(0,float(config.get("_trading_holdings_value",0)))
    trade_spend=invested+sum(o["amount"] for pid,(p,o) in verified.items() if ratings[pid].get("purpose")=="trading")
    excess=[]
    if config.get("auto_withdraw_bids",True) and trade_spend>trade_limit:
        for pid,(p,o) in sorted(verified.items(),key=lambda x:ratings[x[0]].get("score",0)):
            if ratings[pid].get("purpose")!="trading" or not ratings[pid].get("eligible"):continue
            excess.append({"kind":"withdraw_bid","player":p,"player_id":pid,**o,"purpose":"trading",
                           "reason":"Trading-Kapital für vollständige Elf, Bank oder Budgetgrenze freigeben"})
            trade_spend-=o["amount"]
            if trade_spend<=trade_limit:break
    if excess:return {"actions":excess,"ratings":ratings,"blocked":blocked,"combination":basket}
    for p in sorted(tradable,key=lambda p:-ratings[player_id(p)].get("score",0)):
        pid=player_id(p);r=ratings[pid]
        if r.get("purpose")!="trading":continue
        old=verified.get(pid,(None,{"amount":0}))[1]["amount"]
        delta=max(0,r["amount"]-old)
        if delta>available or trade_spend+delta>trade_limit or (not old and free_slots<=0):continue
        if old!=r["amount"]:
            actions.append({"kind":"buy","player":p,"player_id":pid,"amount":r["amount"],"purpose":"trading","reason":r["reason"]})
        available-=delta;trade_spend+=delta
        if not old:free_slots-=1
    return {"actions":actions,"ratings":ratings,"blocked":blocked,"combination":basket,
            "capital":{"budget":budget,"reserve":reserve,"open_bids":exposure,"free":max(0,cash-exposure),
                       "trading_limit":trade_limit,"trading_invested":invested,"notice":"Erwartete Verkaufserlöse nicht eingerechnet"}}

"""Persistent acquisition explanations, verified outcomes and trading exits."""
import hashlib
import json
from pathlib import Path

from base_xi import number, read_cache, write_cache
from decision_engine import player_id, player_name, price_limits, s11_score
from recent_data import timestamp, season_label
from strategy import projection, position, expected, value


def sync_portfolio(data_dir, squad, market, bids, config, now):
    path = Path(data_dir)/"portfolio_journal.json"
    state = read_cache(path)
    holdings = state.setdefault("holdings", {})
    closed = state.setdefault("closed", [])
    current_ids = {player_id(p) for p in squad}
    changes = []
    for p in squad:
        pid = player_id(p)
        acquisition = p.get("acquisition") or {}
        cost = number(acquisition.get("price")) or number(p.get("purchasePrice")) or number(p.get("bp")) or number(p.get("buyPrice"))
        acquired = timestamp(acquisition.get("time"))
        entry = holdings.get(pid)
        # A fresh acquisition of the same player starts a distinct holding.
        if entry and acquired and entry.get("acquired_at") and acquired != entry["acquired_at"]:
            closed.append({**entry, "result":"Besitzwechsel ohne bestätigten Verkaufspreis", "realized_profit":None})
            entry = None
        if not entry:
            bid = bids.get(pid, {})
            attributable = acquired is not None and acquired >= (number(bid.get("time")) or now+1) and cost is not None and cost <= (number(bid.get("amount")) or 0)
            entry = {"id":pid, "name":player_name(p), "first_seen":now,
                     "purpose":bid.get("purpose") if attributable else "unbekannt",
                     "purchase_reason":bid.get("reason") if attributable else "Bereits vorhanden oder Kaufgrund nicht aufgezeichnet",
                     "price_ceiling":bid.get("ceiling") if attributable else None,
                     "policy":{"profit_pct":config.get("trading_take_profit_percent",8),
                               "loss_pct":config.get("trading_stop_loss_percent",5),
                               "hold_days":config.get("trading_max_hold_days",7)},
                     "points_baseline":number(p.get("tp")), "season":season_label(now)}
        if entry.get("season") != season_label(now):
            entry.update(points_baseline=number(p.get("tp")),season=season_label(now))
        role = config.get("player_roles", {}).get(pid)
        entry.setdefault("original_purpose",entry.get("purpose","unbekannt"))
        if role in ("startelf", "trading", "bench"):
            entry["purpose"] = role
            entry["role_source"] = "manuell festgelegt"
        elif entry.get("role_source")=="manuell festgelegt":
            entry["purpose"]=entry.get("original_purpose","unbekannt")
            entry.pop("role_source",None)
        if cost:
            entry["cost"] = cost
        if not entry.get("reference_value") and value(p)>0:
            entry["reference_value"]=value(p)
        if acquired:
            entry["acquired_at"] = acquired
        total = number(p.get("tp"))
        if total is None:
            total = number((p.get("performance") or {}).get("total_points"))
        if entry.get("points_baseline") is None and total is not None:
            entry["points_baseline"] = total
        baseline = entry.get("points_baseline")
        entry["points_since_observation"] = total-baseline if total is not None and baseline is not None and total >= baseline else None
        entry["market_value"] = value(p) or None
        entry["unrealized_profit"] = value(p)-entry["cost"] if value(p) and entry.get("cost") else None
        entry["last_seen"] = now
        observed = {"market_value":value(p), "s11":s11_score(p), "status":p.get("st",p.get("status")),
                    "minutes":(p.get("analysis") or {}).get("recent_minutes")}
        before = entry.get("observed", {})
        for key, val in observed.items():
            if key in before and before[key] is not None and val is not None and val != before[key]:
                if key == "market_value" and abs(val-before[key]) < max(100000, before[key]*.02):
                    continue
                changes.append({"id":pid,"name":player_name(p),"field":key,"before":before[key],"after":val,"time":now})
        entry["observed"] = observed
        holdings[pid] = entry
    # Disappearance alone is not a sale and never proves a sale price.
    roster_reliable = config.get("_roster_reliable", bool(squad))
    if roster_reliable:
        for pid in list(holdings):
            e = holdings[pid]
            if pid not in current_ids:
                if e.get("sale_receipt"):
                    receipt=e["sale_receipt"]
                    closed.append({**e,"sold_at":now,"sale_price":receipt["amount"],
                                   "realized_profit":receipt["amount"]-e["cost"] if e.get("cost") else None,
                                   "result":"Angebotsannahme bestätigt und Spieler nicht mehr im Kader"})
                else:
                    closed.append({**e,"sold_at":now,"realized_profit":None,"result":"Nicht mehr im Kader; Erlös unbekannt"})
                del holdings[pid]
    listings = {player_id(p):p for p in market if player_id(p) in current_ids}
    for pid, e in holdings.items():
        if pid in listings:
            e.setdefault("listed_since",now)
        else:
            e.pop("listed_since",None)
    market_before=state.get("market_observations",{})
    market_now={}
    for p in market:
        pid=player_id(p)
        observed={"market_value":value(p),"s11":s11_score(p),"status":p.get("st",p.get("status")),
                  "minutes":(p.get("analysis") or {}).get("recent_minutes")}
        market_now[pid]=observed
        if pid in current_ids:continue
        before=market_before.get(pid,{})
        for key,val in observed.items():
            old=before.get(key)
            if old is None or val is None or old==val:continue
            if key=="market_value" and abs(val-old)<max(100000,old*.02):continue
            changes.append({"id":pid,"name":player_name(p),"field":key,"before":old,"after":val,"time":now})
    state["market_observations"]=market_now
    state["closed"] = closed[-500:]
    state["changes"] = (state.get("changes",[])+changes)[-100:]
    write_cache(path,state)
    return state


def record_receipts(data_dir, actions, now):
    path=Path(data_dir)/"portfolio_journal.json"
    state=read_cache(path)
    for a in actions:
        if not a.get("ok"):
            continue
        e=state.get("holdings",{}).get(a.get("player_id"))
        if not e:
            continue
        if a.get("action") in ("accept_offer","instant_sell") and (number(a.get("amount")) or 0)>0:
            e["sale_receipt"]={"amount":a["amount"],"time":now}
        if a.get("action") in ("list","adjust_price"):
            e["last_asking_price"]=a.get("amount")
    write_cache(path,state)


def exit_plan(p, entry, config, now):
    cost=number(entry.get("cost"))
    policy=entry.get("policy",{})
    trading=entry.get("purpose")=="trading"
    profit=float(config.get("trading_take_profit_percent",8))
    loss=float(config.get("trading_stop_loss_percent",policy.get("loss_pct",5)))
    market_basis=config.get("sale_price_basis","market")=="market"
    reference=number(entry.get("reference_value")) if market_basis else cost
    acquired=entry.get("acquired_at")
    hold_days=float(config.get("trading_max_hold_days",policy.get("hold_days",7)))
    reset=timestamp(config.get("winter_reset_at")) if config.get("winter_reset_enabled") else None
    deadline=min(acquired+hold_days*86400,reset) if acquired and reset else acquired+hold_days*86400 if acquired else None
    reasons=[]
    if trading and reference:
        if value(p)>=reference*(1+profit/100):reasons.append("Trading-Kursziel erreicht")
        if value(p)<=reference*(1-loss/100):reasons.append("Trading-Rückgangsgrenze erreicht")
        if deadline and now>=deadline:reasons.append("Haltedauer oder Reset-Frist erreicht")
        trend=number((p.get("base_xi") or {}).get("trend_24h"))
        if trend is not None and trend<0:reasons.append("Trading-Trend negativ")
    listed_since=entry.get("listed_since")
    slow=listed_since is not None and now-listed_since>=int(config.get("slow_seller_days",3))*86400
    if slow:reasons.append("Seit mehreren Tagen gelistet; Preis neu bewerten")
    limits=price_limits(p,config,is_core=False)
    stop_floor=round(reference*(1-loss/100)) if reference else None
    goal=round(reference*(1+profit/100)) if reference else None
    floor=limits["accept"]
    asking=limits["asking"]
    if trading and reference:
        floor=(round(value(p)*(1-loss/100)) if market_basis else stop_floor) if reasons else goal
        asking=max(floor,round(value(p))) if reasons else max(goal,asking)
    elif slow:
        reduction=min(10, max(1,int((now-listed_since)/86400)-int(config.get("slow_seller_days",3))+1))
        asking=max(floor,round(asking*(1-reduction/100)))
    return {"player_id":player_id(p),"name":player_name(p),"purpose":entry.get("purpose","unbekannt"),
            "cost":cost,"goal":goal if trading else limits["accept"],"stop_floor":stop_floor if trading else None,
            "reference_value":reference,"reference_basis":"Marktwert bei erster Erfassung" if market_basis else "Einkaufspreis",
            "deadline":deadline,"reasons":reasons,"slow_seller":slow,"accept":floor,"asking":asking,
            "needs_exit":bool(reasons) and trading,"price_known":bool(cost),
            "notice":"Verlustgrenze ist eine Ausstiegsregel, keine garantierte Ausführung zum Grenzpreis"}


def apply_exits(plan, squad, market, journal, config, near_matchday, now):
    exits={player_id(p):exit_plan(p,journal.get("holdings",{}).get(player_id(p),{}),config,now) for p in squad}
    plan["actions"]=[a for a in plan["actions"] if not (
        a["kind"] in ("accept_offer","instant_sell") and exits.get(a.get("player_id"),{}).get("purpose")=="trading"
        and (number(a.get("amount")) or 0)<exits[a["player_id"]]["accept"])]
    # Start with already planned sales so two policies cannot spend the same depth.
    selling={a.get("player_id") for a in plan["actions"] if a["kind"] in ("accept_offer","instant_sell")}
    remaining=[p for p in squad if player_id(p) not in selling]
    for pid, ex in exits.items():
        if ex["purpose"]!="trading" and not ex["slow_seller"]:
            continue
        if pid in set(map(str,config.get("protected_players",[]))):
            continue
        for a in plan["actions"]:
            if a.get("player_id")==pid and a["kind"] in ("list","adjust_price"):
                a["amount"]=ex["asking"]
                a["reason"]="; ".join(ex["reasons"]) or "Trading-Gewinnziel"
        if not ex["needs_exit"] or near_matchday or pid in selling:
            continue
        after=[p for p in remaining if player_id(p)!=pid]
        if len(after)<int(config.get("minimum_squad_size",11)) or not projection(after)["complete"]:
            continue
        listing=next((p for p in market if player_id(p)==pid),None)
        if not listing or not config.get("auto_accept_offers",True):continue
        owner=listing.get("userId") or listing.get("ui") or listing.get("u")
        owner=owner.get("i",owner.get("id")) if isinstance(owner,dict) else owner
        if str(owner)!=str(config.get("_user_id")):continue
        offers=[o for o in (listing.get("ofs") or listing.get("offers") or []) if isinstance(o,dict)]
        offers=[o for o in offers if (number(o.get("price",o.get("prc",o.get("uop")))) or 0)>=ex["accept"]]
        if offers:
            offer=max(offers,key=lambda o:number(o.get("price",o.get("prc",o.get("uop")))) or 0)
            amount=number(offer.get("price",offer.get("prc",offer.get("uop"))))
            plan["actions"]=[a for a in plan["actions"] if a.get("player_id")!=pid]
            plan["actions"].append({"kind":"accept_offer","player":listing,"player_id":pid,"offer":offer,
                                   "amount":amount,"reason":"; ".join(ex["reasons"]),"purpose":"trading"})
            remaining=after
            selling.add(pid)
    return list(exits.values())


def league_checks(squad, market, budget, config, live, now):
    current=projection(squad)
    checks=[]
    if not current["complete"]:checks.append("Elf unvollständig: "+str(current["missing"]))
    if budget is None:checks.append("Kontostand unbekannt")
    elif budget<0:checks.append("Kontostand negativ: vor Spieltagsbeginn ausgleichen")
    low=[player_name(p) for p in current["players"] if (s11_score(p) or 0)<3]
    if low:checks.append("Einsatzchance prüfen: "+", ".join(low))
    submitted=config.get("_submitted_lineup")
    if not isinstance(submitted,list):checks.append("Tatsächlich aufgestellte Elf nicht verifizierbar")
    else:
        ids={str(x.get("pi")) for x in submitted if isinstance(x,dict) and x.get("pi")}
        if len(ids)!=11:checks.append(f"Tatsächlich aufgestellt: {len(ids)}/11 Spieler")
        elif ids!={player_id(p) for p in current["players"]}:checks.append("Aufgestellte Elf weicht von der vorgeschlagenen besten Elf ab")
    kickoff=timestamp(live.get("next_kickoff"))
    if not kickoff:checks.append("Nächster Anpfiff unbekannt")
    mvp=config.get("mvp_confirmation") or {}
    confirmed=(config.get("mvp_rule_enabled",True) and mvp.get("confirmed") is True
               and mvp.get("player_id") and mvp.get("matchday") and mvp.get("source")
               and not mvp.get("completed") and timestamp(mvp.get("ended_at")) is not None and timestamp(mvp["ended_at"])<=now)
    mvp_id=str(mvp.get("player_id")) if confirmed else None
    owned=any(player_id(p)==mvp_id for p in squad)
    if config.get("mvp_rule_enabled",True):
        checks.append("MVP-Verkauf als erledigt bestätigt" if mvp.get("completed") else "Bestätigten Spieltags-MVP an KICKBASE verkaufen: "+mvp_id if owned else
                      "MVP nicht im eigenen Kader" if confirmed else "MVP-Regel: endgültigen MVP und Spieltagsende noch bestätigen")
    reset=timestamp(config.get("winter_reset_at")) if config.get("winter_reset_enabled") else None
    if config.get("winter_reset_enabled"):
        checks.append("Winterreset-Datum fehlt" if reset is None else f"Winterreset in {max(0,(reset-now)/86400):.1f} Tagen")
    return {"checks":checks,"kickoff":kickoff,"urgent":kickoff is not None and 0<=kickoff-now<=48*3600,
            "mvp_id":mvp_id if owned else None,"mvp":mvp,"winter_reset":reset,"lineup":current,
            "notice":"MVP wird nicht aus unvollständigen Punkten geschätzt; Bestätigung im Regelbereich erforderlich"}


def report(journal):
    confirmed=[x for x in journal.get("closed",[]) if x.get("realized_profit") is not None]
    grouped={}
    for x in confirmed:
        purpose=x.get("purpose","unbekannt")
        g=grouped.setdefault(purpose,{"trades":0,"profit":0,"wins":0})
        g["trades"]+=1;g["profit"]+=x["realized_profit"];g["wins"]+=int(x["realized_profit"]>0)
    return {"realized_profit":sum(x["realized_profit"] for x in confirmed),"confirmed_trades":len(confirmed),
            "unknown_results":sum(x.get("realized_profit") is None for x in journal.get("closed",[])),
            "groups":grouped,"holdings":list(journal.get("holdings",{}).values()),"closed":journal.get("closed",[])[-30:],
            "changes":journal.get("changes",[])[-30:],"notice":"Erfasste Ergebnisse seit Beginn der Aufzeichnung; fehlende Erlöse zählen nicht als null Euro"}


def shadow_trial(data_dir, combinations, players, config, now):
    path=Path(data_dir)/"shadow_trials.json"
    state=read_cache(path)
    rows=state.get("rows",[])
    values={player_id(p):value(p) for p in players if value(p)>0}
    for row in rows:
        # Latest known mark, never fake fills or winning auctions.
        if all(pid in values for pid in row["ids"]):
            row.update(marked_at=now,hypothetical_change=sum(values[p] for p in row["ids"])-row["cost"])
    settings={k:v for k,v in config.items() if not k.startswith("_") and k in
              ("minimum_cash","maximum_overpay_percent","bench_size","combination_size","minimum_starting_probability","trial_min_s11","trial_minimum_cash")}
    digest=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:12]
    for variant,result in combinations.items():
        key=f"{int(now//86400)}:{variant}:{digest}"
        if result.get("ids") and not any(x["key"]==key for x in rows):
            rows.append({"key":key,"variant":variant,"created_at":now,"ids":result["ids"],"cost":result["cost"],
                         "settings":settings,"hypothetical_change":None,"expected_gain":result["gain"]})
    rows=[r for r in rows if now-r["created_at"]<60*86400][-180:]
    write_cache(path,{"rows":rows})
    return {"rows":rows[-20:],"notice":"Probelauf ohne Aufträge: Marktwertänderung eines hypothetischen Warenkorbs, keine echten Gewinne; Zuschlag und Verkauf nicht simuliert"}

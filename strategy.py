"""Explainable estimates and bounded whole-roster purchase search.

Scores are heuristics, not promises. Search is exhaustive within a displayed
shortlist (up to 24 candidates, up to three purchases), not a global optimum.
"""
from collections import Counter
from itertools import combinations

from base_xi import number
from decision_engine import FORMATIONS, player_id, player_name, s11_score
from recent_data import timestamp


def position(p):
    return int(number(p.get("position", p.get("pos"))) or 0)


def value(p):
    return number(p.get("marketValue")) or number(p.get("mv")) or 0


def expected(p):
    estimate = (p.get("analysis") or {}).get("expected_points")
    if estimate is not None:
        return estimate
    avg = number((p.get("performance") or {}).get("average_points"))
    if avg is None:
        avg = number(p.get("ap")) or number((p.get("base_xi") or {}).get("average_points")) or 0
    return max(0, avg) * ((s11_score(p) or 0) / 5)


def team_profiles(source):
    teams = {}
    for p in source.get("players", {}).values() if source.get("available") else []:
        pts = number(p.get("avgPoints"))
        if pts is not None and (number(p.get("matchesPlayed")) or 0) >= 2:
            teams.setdefault(str(p.get("teamId", "")), []).append(pts)
    scores = {k: sum(sorted(v, reverse=True)[:11]) / 11 for k, v in teams.items() if len(v) >= 11}
    average = sum(scores.values()) / len(scores) if scores else 0
    return {k: max(.85, min(1.15, 1 + (average-v) / max(average, 1) * .15)) for k, v in scores.items()}


def annotate(players, source, now, config=None):
    config = config or {}
    profiles = team_profiles(source)
    output = []
    for p in players:
        b, recent = p.get("base_xi") or {}, p.get("recent") or {}
        rows = recent.get("rows", []) if recent.get("available") else []
        rows = rows[-5:]
        known = [(i+1, number(x.get("points"))) for i, x in enumerate(rows) if number(x.get("points")) is not None]
        recent_points = sum(w*v for w, v in known) / sum(w for w, _ in known) if known else None
        mins = [number(x.get("minutes")) for x in rows[-3:]]
        minutes_complete = len(mins) >= 3 and all(v is not None for v in mins)
        avg_minutes = sum(mins)/len(mins) if minutes_complete else None
        season = number((p.get("performance") or {}).get("average_points"))
        if season is None:
            season = number(b.get("average_points"))
        baseline = (.7*recent_points + .3*season) if recent_points is not None and season is not None else (recent_points if recent_points is not None else season)
        upcoming = recent.get("upcoming", []) if recent.get("available") else []
        opponents = []
        for row in upcoming[:3]:
            opp = row["away"] if row.get("team") == row.get("home") else row["home"] if row.get("team") == row.get("away") else ""
            opponents.append({"id": opp, "date": row.get("date"), "factor": profiles.get(opp)})
        if not opponents:
            for row in (b.get("match_preview") or [])[:3]:
                if isinstance(row, dict):
                    opp = str(row.get("opp", ""))
                    opponents.append({"id": opp, "date": None, "factor": profiles.get(opp)})
        factors = [r["factor"] for r in opponents if r["factor"] is not None]
        factor = sum(factors)/len(factors) if factors else 1
        additional = [x for x in config.get("additional_fixtures",[]) if isinstance(x,dict)
                      and str(x.get("team_id"))==str(p.get("tid") or p.get("teamId") or b.get("team_id"))
                      and x.get("source") and timestamp(x.get("date")) and now<timestamp(x["date"])<now+21*86400]
        dates = sorted([x["timestamp"] for x in upcoming if x.get("timestamp")]+[timestamp(x["date"]) for x in additional])
        congestion = any(0 < b-a <= 4*86400 for a, b in zip(dates, dates[1:]))
        rotation = (sum(v < 60 for v in mins)/len(mins)) if minutes_complete else None
        risk = []
        if rotation is not None and rotation >= 2/3:
            risk.append("Mindestens zwei der letzten drei Spiele unter 60 Minuten")
        if congestion:
            risk.append("Kurzer Abstand zwischen bekannten Pflichtspielen")
        status = number(p.get("st", p.get("status")))
        unavailable = (status is not None and status != 0) or (number(b.get("status")) not in (None, 0))
        if unavailable:
            risk.append("Eingeschränkte Verfügbarkeit gemeldet")
        score = s11_score(p)
        estimate = max(0, baseline or 0) * ((score or 0)/5) * factor * (.95 if congestion else 1)
        if unavailable:
            estimate = 0
        p = {**p, "analysis": {"expected_points": round(estimate, 2), "estimate": True,
            "recent_points": recent_points, "recent_minutes": avg_minutes,
            "minutes_complete": minutes_complete, "rows": rows, "season_points": season,
            "rotation_indicator": rotation, "risks": risk, "opponents": opponents,
            "opponent_factor": round(factor, 3), "opponent_basis": "Punkteprofil der elf punktbesten Vereinsspieler, keine Tabellenposition",
            "congestion": congestion, "international_schedule": additional or "Keine zusätzlichen Pflichtspiele hinterlegt; internationale Belastung unbekannt",
            "ages_hours": {"market": age(b.get("checked_at"),now) if p.get("market_value_source")=="Base-XI" else 0,
                           "s11":0 if (p.get("s11") or {}).get("source")=="KICKBASE" else age((p.get("s11") or {}).get("checked_at"), now),
                           "base_xi": age(b.get("checked_at"), now), "minutes": age(recent.get("checked_at"), now)},
            "confidence": "mittel" if minutes_complete and score is not None else "gering"}}
        output.append(p)
    return output


def age(stamp, now):
    parsed = timestamp(stamp)
    return round(max(0, now-parsed)/3600, 2) if parsed is not None else None


def projection(players):
    unique = {player_id(p): p for p in players if player_id(p)}
    by_pos = {pos: sorted([p for p in unique.values() if position(p) == pos], key=lambda p: (-expected(p), player_id(p))) for pos in range(1, 5)}
    best = None
    for d, m, f in FORMATIONS:
        needs = {1: 1, 2: d, 3: m, 4: f}
        selected = [p for pos, count in needs.items() for p in by_pos[pos][:count]]
        missing = {str(pos): max(0, count-len(by_pos[pos])) for pos, count in needs.items()}
        score = sum(expected(p) for p in selected)
        rank = (len(selected), score)
        if best is None or rank > best[0]:
            best = (rank, {"players": selected, "formation": f"{d}-{m}-{f}", "complete": len(selected)==11,
                           "filled": len(selected), "expected_points": round(score, 2), "missing": missing})
    result = best[1]
    result["minimum_shortfall"]=sum(max(0,n-len(by_pos[pos])) for pos,n in {1:1,2:3,3:3,4:1}.items())
    ids = {player_id(p) for p in result["players"]}
    result["bench"] = [p for p in unique.values() if player_id(p) not in ids]
    return result


def choose_combination(players, squad, ratings, budget, config, reserved=0):
    current = projection(squad)
    allowed = max(0, (number(budget) or 0)-max(0, number(config.get("minimum_cash",1_000_000)) or 0)-reserved)
    count_limit = max(1, min(3, int(config.get("combination_size", 3))))
    slots = max(0, int(config.get("maximum_squad_size", 18))-len(squad))
    count_limit = min(count_limit, slots)
    eligible = [p for p in players if ratings.get(player_id(p), {}).get("eligible")
                and ratings[player_id(p)].get("purpose") in ("startelf", "bench")]
    shortlist = []
    for pos in range(1, 5):
        group = sorted([p for p in eligible if position(p)==pos], key=lambda p: (-expected(p)/max(ratings[player_id(p)]["amount"], 1), ratings[player_id(p)]["amount"]))
        # Include cheap depth and the highest absolute-quality alternative.
        picked = group[:5] + sorted(group, key=expected, reverse=True)[:1]
        shortlist.extend({player_id(p):p for p in picked}.values())
    desired_bench = max(0, min(4, int(config.get("bench_size", 2))))
    def evaluate(combo):
        cost = sum(ratings[player_id(p)]["amount"] for p in combo)
        if cost > allowed:
            return None
        all_players = squad+list(combo)
        counts = Counter(str(p.get("tid") or p.get("teamId") or (p.get("base_xi") or {}).get("team_id") or "") for p in all_players)
        if any(t and n > int(config.get("maximum_per_club", 3)) for t,n in counts.items()):
            return None
        projected = projection(all_players)
        usable_bench = [p for p in projected["bench"] if (s11_score(p) or 0)>=3 and value(p)<=int(config.get("bench_player_budget", 4_000_000))]
        depth = min(desired_bench, len({position(p) for p in usable_bench}))
        rank = (projected["filled"], -projected["minimum_shortfall"], projected["expected_points"] + depth*float(config.get("bench_value_points", 8)), -cost)
        return rank, projected, cost
    base = evaluate(())
    if base is None:
        base = ((current["filled"], -current["minimum_shortfall"], current["expected_points"], 0), current, 0)
    scored = [(base, ())]
    for size in range(1, count_limit+1):
        for combo in combinations(shortlist, size):
            result = evaluate(combo)
            if result is not None:
                scored.append((result, combo))
    scored.sort(key=lambda x:x[0][0], reverse=True)
    (rank, target, cost), chosen = scored[0]
    alternatives = [{"players": [{"id":player_id(p),"name":player_name(p)} for p in combo],
                     "cost":r[2], "expected_points":r[1]["expected_points"], "filled":r[1]["filled"]}
                    for r, combo in scored[:5]]
    return {"ids": [player_id(p) for p in chosen], "cost":cost, "current":current,
            "target":target, "gain":round(target["expected_points"]-current["expected_points"],2),
            "alternatives":alternatives, "shortlist_size":len(shortlist), "evaluated":len(scored),
            "search_limit":count_limit, "available":allowed,
            "notice":"Schätzung; beste gefundene Kombination innerhalb der begrenzten Auswahlliste"}


def price_ceiling(p, alternatives, squad, hard_limit, config):
    current = projection(squad)
    incumbent = min([expected(x) for x in current["players"] if position(x)==position(p)], default=0)
    gain = max(0, expected(p)-incumbent)
    # The suggested ceiling may be below the asking price: then do not bid.
    performance_limit = value(p) + gain*max(0, float(config.get("euros_per_extra_point", 30_000)))
    substitutes = [x for x in alternatives if player_id(x)!=player_id(p) and position(x)==position(p)
                   and expected(x)>=expected(p)*.95 and (s11_score(x) or 0)>=3]
    alternative_limit = min([max(value(x),number(x.get("prc")) or value(x))*expected(p)/max(expected(x),1) for x in substitutes], default=hard_limit)
    return int(min(hard_limit, performance_limit, alternative_limit)), round(gain,2)

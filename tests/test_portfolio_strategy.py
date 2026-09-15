import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import app
import dashboard
from base_xi import read_cache
from bid_policy import plan_bids, assess
from decision_engine import price_limits, build_trade_plan
from portfolio import sync_portfolio, record_receipts, exit_plan, apply_exits, report, league_checks, shadow_trial
from recent_data import parse_performance, enrich_recent
from strategy import annotate, projection, choose_combination

NOW=datetime(2026,9,15,tzinfo=timezone.utc).timestamp()


def player(pid, pos=3, points=70, price=1_000_000, team=None):
    return {"i":str(pid),"n":"Spieler "+str(pid),"pos":pos,"mv":price,"prc":price,"prob":5,"st":0,"exs":7200,
            "tid":str(team or pid),"ap":points,"tp":points*3,
            "base_xi":{"available":True,"status":0,"average_points":points,"average_minutes":80,"matches":3,
                       "trend_24h":100000,"ki_trend":50000,"fair_value":price*2},
            "analysis":{"expected_points":points}}


def squad():
    return [player("g",1),*[player("d"+str(i),2) for i in range(4)],
            *[player("m"+str(i),3) for i in range(4)],player("f1",4),player("f2",4)]


def ratings(ps):
    return {p["i"]:{"eligible":True,"purpose":"startelf","amount":p["prc"],"ceiling":p["prc"]*1.08,"score":p["ap"]} for p in ps}


class RecentTests(unittest.TestCase):
    def payload(self):
        return {"it":[{"ti":"2026/27","ph":[
            {"day":1,"mp":"0'","p":0,"ap":999,"tp":9999,"t1g":1,"t2g":0,"md":"2026-08-23T13:30:00Z"},
            {"day":2,"mp":"90'","p":100,"t1g":1,"t2g":1,"md":"2026-08-30T13:30:00Z"},
            {"day":3,"mp":None,"p":25,"t1g":0,"t2g":1,"md":"2026-09-12T13:30:00Z"},
            {"day":4,"md":"2026-09-18T18:30:00Z","t1":"1","t2":"2","pt":"1"}]},
            {"ti":"2025/26","ph":[{"day":34,"mp":"90'","p":999,"t1g":1,"t2g":0}]}]}

    def test_minutes_zero_is_known_missing_is_not_zero_and_prior_season_excluded(self):
        rows,future=parse_performance(self.payload(),NOW)
        self.assertEqual([x["points"] for x in rows],[0,100,25])
        self.assertEqual([x["minutes"] for x in rows],[0,90,None])
        self.assertEqual(future[0]["day"],4)

    def test_live_game_not_used_as_finished_form(self):
        payload={"it":[{"ti":"2026/27","ph":[{"day":3,"mp":"0'","p":0,"t1g":0,"t2g":0,
                  "md":datetime.fromtimestamp(NOW-1800,timezone.utc).isoformat()}]}]}
        self.assertEqual(parse_performance(payload,NOW)[0],[])

    def test_bounded_fetch_and_missing_source_stays_unknown(self):
        client=Mock();client.get_optional.return_value={"ok":True,"data":self.payload()}
        with tempfile.TemporaryDirectory() as d:
            ps=[player(i) for i in range(8)]
            first=enrich_recent(client,"L",ps,d,now=NOW)
            self.assertEqual(client.get_optional.call_count,4)
            self.assertEqual(sum(x["recent"]["available"] for x in first),4)
            enrich_recent(client,"L",ps,d,now=NOW+300)
            self.assertEqual(client.get_optional.call_count,8)
            client.get_optional.return_value={"ok":False}
            stale=enrich_recent(client,"L",ps,d,now=NOW+7*3600)
            self.assertFalse(any(x["recent"]["available"] for x in stale))

    def test_three_zero_minutes_reject_xi_and_unknown_minutes_not_fabricated(self):
        p=player("zero",price=4_000_000)
        p["recent"]={"available":True,"rows":[{"day":i,"minutes":0,"points":0} for i in (1,2,3)]}
        p=annotate([p],{},NOW)[0]
        self.assertEqual(p["analysis"]["recent_minutes"],0)
        self.assertFalse(assess(p,{})["eligible"])
        p["recent"]["rows"][0]["minutes"]=None
        self.assertIsNone(annotate([p],{},NOW)[0]["analysis"]["recent_minutes"])

    def test_extra_verified_fixture_affects_congestion_only_for_correct_club(self):
        p=player("p",team="club")
        p["recent"]={"available":True,"rows":[],"upcoming":[{"timestamp":NOW+3*86400,"date":"2026-09-18T00:00:00Z","team":"club","home":"club","away":"x"}]}
        cfg={"additional_fixtures":[{"team_id":"club","date":"2026-09-20T00:00:00Z","source":"Verein"}]}
        self.assertTrue(annotate([p],{},NOW,cfg)[0]["analysis"]["congestion"])
        cfg["additional_fixtures"][0]["team_id"]="other"
        self.assertFalse(annotate([p],{},NOW,cfg)[0]["analysis"]["congestion"])


class CombinationTests(unittest.TestCase):
    def test_two_affordable_upgrades_beat_one_star(self):
        roster=squad();roster[1]["analysis"]["expected_points"]=10;roster[5]["analysis"]["expected_points"]=10
        ps=[player("a",2,100,2_000_000),player("b",3,100,2_000_000),player("star",3,160,4_000_000)]
        result=choose_combination(ps,roster,ratings(ps),4_000_000,{"minimum_cash":0,"bench_size":0})
        self.assertEqual(set(result["ids"]),{"a","b"})
        self.assertEqual(result["cost"],4_000_000)

    def test_vacant_striker_before_luxury_upgrade(self):
        roster=[p for p in squad() if p["pos"]!=4]
        ps=[player("forward",4,60,2_000_000),player("luxury",3,200,2_000_000)]
        r=choose_combination(ps,roster,ratings(ps),2_000_000,{"minimum_cash":0})
        self.assertEqual(r["ids"],["forward"])
        self.assertEqual(r["target"]["minimum_shortfall"],0)
        self.assertEqual(r["target"]["filled"],10)
        roster.append(player("extra",3))
        r=choose_combination(ps,roster,ratings(ps),2_000_000,{"minimum_cash":0})
        self.assertTrue(r["target"]["complete"])

    def test_reserve_club_and_roster_limits(self):
        roster=squad();roster[:3]=[{**p,"tid":"one"} for p in roster[:3]]
        ps=[player("blocked",3,200,1_000_000,team="one")]
        r=choose_combination(ps,roster,ratings(ps),10_000_000,{})
        self.assertEqual(r["ids"],[])
        ps[0]["tid"]="other"
        r=choose_combination(ps,roster,ratings(ps),2_000_000,{},reserved=1_000_000)
        self.assertEqual(r["ids"],[])
        r=choose_combination(ps,roster,ratings(ps),10_000_000,{"maximum_squad_size":11})
        self.assertEqual(r["ids"],[])

    def test_better_bid_is_withdrawn_before_reallocation(self):
        old=player("old",3,90,2_000_000);old.update(uoid="me",uop=2_000_000)
        new=player("new",3,140,2_000_000)
        result=plan_bids([old,new],squad(),{"minimum_cash":0},"me",2_000_000)
        self.assertEqual([a["kind"] for a in result["actions"]],["withdraw_bid"])
        self.assertEqual(result["actions"][0]["player_id"],"old")

    def test_incomplete_xi_blocks_trading_capital(self):
        trader=player("trader",3,0,500000);trader["base_xi"].update(matches=0,average_minutes=0)
        r=plan_bids([trader],[],{},"me",10_000_000)
        self.assertEqual(r["actions"],[])
        self.assertEqual(r["capital"]["trading_limit"],0)

    def test_reset_blocks_late_investment(self):
        p=player("new",3,180)
        cfg={"_now":NOW,"winter_reset_enabled":True,"winter_reset_at":"2026-09-16T00:00:00Z"}
        r=plan_bids([p],squad(),cfg,"me",10_000_000)
        self.assertEqual(r["actions"],[])
        self.assertTrue(any("Winterreset" in b["reason"] for b in r["blocked"]))


class JournalTests(unittest.TestCase):
    def test_bid_success_is_not_purchase_or_profit(self):
        p=player("x")
        bids={"x":{"time":NOW-10,"amount":1_000_000,"purpose":"trading","reason":"Trend"}}
        with tempfile.TemporaryDirectory() as d:
            j=sync_portfolio(d,[p],[],bids,{},NOW)
            self.assertEqual(j["holdings"]["x"]["purpose"],"unbekannt")
            self.assertNotIn("cost",j["holdings"]["x"])
            self.assertEqual(report(j)["realized_profit"],0)

    def test_profit_only_after_receipt_and_roster_confirmation(self):
        p=player("x");p["acquisition"]={"price":800000,"time":NOW-5}
        bids={"x":{"time":NOW-10,"amount":1_000_000,"purpose":"trading","reason":"Trend"}}
        cfg={"_roster_reliable":True}
        with tempfile.TemporaryDirectory() as d:
            j=sync_portfolio(d,[p],[],bids,cfg,NOW)
            self.assertEqual(j["holdings"]["x"]["purpose"],"trading")
            record_receipts(d,[{"ok":True,"player_id":"x","action":"accept_offer","amount":900000}],NOW)
            j=sync_portfolio(d,[p],[],bids,cfg,NOW+300)
            self.assertEqual(report(j)["confirmed_trades"],0)
            j=sync_portfolio(d,[],[],bids,cfg,NOW+600)
            self.assertEqual(report(j)["realized_profit"],100000)
            j=sync_portfolio(d,[],[],bids,cfg,NOW+900)
            self.assertEqual(report(j)["confirmed_trades"],1)

    def test_missing_roster_does_not_fabricate_sale(self):
        p=player("x");p["purchasePrice"]=900000
        with tempfile.TemporaryDirectory() as d:
            sync_portfolio(d,[p],[],{}, {},NOW)
            j=sync_portfolio(d,[],[],{}, {"_roster_reliable":False},NOW+300)
            self.assertIn("x",j["holdings"])
            j=sync_portfolio(d,[],[],{}, {"_roster_reliable":True},NOW+600)
            self.assertIsNone(j["closed"][0]["realized_profit"])

    def test_eight_percent_goal_and_current_market_exit_ignores_sunk_cost(self):
        p=player("x",price=700000)
        entry={"purpose":"trading","cost":2_000_000,"reference_value":1_000_000,"acquired_at":NOW-8*86400}
        ex=exit_plan(p,entry,{},NOW)
        self.assertEqual(ex["goal"],1_080_000)
        self.assertTrue(ex["needs_exit"])
        self.assertLess(ex["accept"],700000)
        self.assertEqual(ex["cost"],2_000_000)

    def test_unknown_acquisition_does_not_invent_holding_age(self):
        p=player("x")
        ex=exit_plan(p,{"purpose":"trading","reference_value":1_000_000},{},NOW)
        self.assertIsNone(ex["deadline"])
        self.assertFalse(ex["needs_exit"])

    def test_purchase_price_no_longer_blocks_market_based_sale(self):
        p=player("x",price=1_000_000);p["purchasePrice"]=4_000_000
        self.assertLess(price_limits(p,{})["accept"],4_000_000)
        self.assertGreaterEqual(price_limits(p,{"sale_price_basis":"purchase"})["accept"],4_000_000)

    def test_trading_exit_cannot_destroy_xi_or_sell_foreign_listing(self):
        roster=squad();p=roster[0];p.update(u="me",offers=[{"id":"bidder","prc":1_000_000}])
        journal={"holdings":{p["i"]:{"purpose":"trading","reference_value":2_000_000,"cost":2_000_000}}}
        plan={"actions":[],"blocked":[]}
        apply_exits(plan,roster,[p],journal,{"_user_id":"me"},False,NOW)
        self.assertFalse(any(a["kind"]=="accept_offer" for a in plan["actions"]))

    def test_protected_listing_cannot_be_sold(self):
        roster=squad()+[player("spare",3)];p=roster[-1];p.update(u="me",offers=[{"id":"b","prc":10_000_000}])
        plan=build_trade_plan([p],roster,{"protected_players":["spare"]},"me")
        self.assertFalse(any(a["player_id"]=="spare" for a in plan["actions"]))

    def test_mvp_requires_final_confirmation_and_respects_completion(self):
        p=player("x")
        cfg={"mvp_confirmation":{"player_id":"x","matchday":3,"source":"KICKBASE","ended_at":"2026-09-13T20:00:00Z"}}
        self.assertIsNone(league_checks([p],[],0,cfg,{},NOW)["mvp_id"])
        cfg["mvp_confirmation"]["confirmed"]=True
        self.assertEqual(league_checks([p],[],0,cfg,{},NOW)["mvp_id"],"x")
        cfg["mvp_confirmation"]["completed"]=True
        self.assertIsNone(league_checks([p],[],0,cfg,{},NOW)["mvp_id"])

    def test_shadow_marks_are_not_realized_and_unknown_quotes_stay_unknown(self):
        combo={"ids":["x"],"cost":1_000_000,"gain":50}
        with tempfile.TemporaryDirectory() as d:
            r=shadow_trial(d,{"Probe":combo},[],{},NOW)
            self.assertIsNone(r["rows"][0]["hypothetical_change"])
            r=shadow_trial(d,{"Probe":combo},[player("x",price=1_100_000)],{},NOW+300)
            self.assertEqual(len(r["rows"]),1)
            self.assertEqual(r["rows"][0]["hypothetical_change"],100000)
            self.assertNotIn("realized_profit",r["rows"][0])


class IntegrationTests(unittest.TestCase):
    def test_dashboard_saves_rules_and_rejects_incomplete_mvp(self):
        with tempfile.TemporaryDirectory() as d, patch.object(dashboard,"CONFIG",Path(d)/"config.json"):
            client=dashboard.app.test_client()
            self.assertEqual(client.get('/planner.js').status_code,200)
            r=client.post('/api/config',json={"sale_price_basis":"market","trading_take_profit_percent":8,"trial_min_s11":4})
            self.assertEqual(r.status_code,200)
            saved=json.loads((Path(d)/"config.json").read_text())
            self.assertEqual(saved["trading_take_profit_percent"],8)
            r=client.post('/api/config',json={"mvp_confirmation":{"confirmed":True,"player_id":"x"}})
            self.assertEqual(r.status_code,400)

    def test_safe_check_uses_real_budget_source_and_new_pipeline_without_trading(self):
        cfg={"league_name":"Testliga","mode":"live","trading_enabled":True,"minimum_cash":1_000_000}
        roster=squad()
        client=Mock()
        client.login.return_value={"u":{"i":"me"},"leagues":[{"i":"L","n":"Testliga"}]}
        client.get.return_value={"it":[player("new",3,200)]}
        def get_optional(*paths):
            path=paths[0]
            if path=='/v4/leagues/selection':data={"it":[{"i":"L","n":"Testliga","b":0}]}
            elif path.endswith('/squad'):data={"it":roster}
            elif path.endswith('/lineup/overview'):data={"b":99_000_000,"lp":[{"pi":p["i"],"pos":p["pos"]} for p in roster]}
            else:return {"ok":False,"data":{}}
            return {"ok":True,"data":data}
        client.get_optional.side_effect=get_optional
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'config.json').write_text(json.dumps(cfg))
            with patch.object(app,'ROOT',root),patch.object(app,'DATA',root/'data'),patch.object(app,'KickbaseClient',return_value=client),patch.object(app.keyring,'get_password',return_value='local-test'),patch.object(app,'fetch_ligainsider',return_value={}),patch.object(app,'fetch_kickbest',return_value={}),patch.object(app,'fetch_base_xi',return_value={"available":False,"players":{}}),patch.object(app,'bundesliga_live',return_value={}),patch.object(app,'news_monitor',return_value=({"items":[]},[])):
                app.run_once(safe_check=True)
            state=json.loads((root/'data/state.json').read_text())
            self.assertEqual(state['account_budget'],0)
            self.assertEqual(len(state['squad']),11)
            self.assertIn('analysis',state['squad'][0])
            client.write.assert_not_called()
            self.assertEqual(state['notification']['reason'],'Installationstest ohne E-Mail')


if __name__=='__main__':unittest.main()

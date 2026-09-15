import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

import app
from base_xi import fetch_base_xi, enrich_base_xi, fetch_base_xi_forms, read_cache
from bid_policy import assess, plan_bids, own_offer, login_user_id
from notifications import hourly_digest


# Shape checked against the public Base-XI API, without personal account data.
ROW = {"id": "7226", "name": "Harry Kane", "marketValue": 66051468,
       "avgMinutes": 77, "avgPoints": 134, "matchesPlayed": 3, "starts": 2,
       "totalPoints": 403, "medianPoints": 204, "consistencyFrom": "vorsaison",
       "pointsPerMio": 3.3, "pointsPerMioFrom": "vorsaison", "mvTrend": -241732,
       "kiTrend": -227789, "fairValue": 177900407, "status": 0, "isHot": False,
       "gamble": 0, "position": "Sturm"}


def candidate(pid="10", own=False, **changes):
    p = {"i": pid, "fn": "Test", "n": "Spieler", "pos": 3, "mv": 1_000_000,
         "prc": 1_000_000, "prob": 5, "st": 0, "exs": 36000,
         "base_xi": {"available": True, "status": 0, "matches": 3,
                     "average_minutes": 75, "average_points": 100,
                     "trend_24h": 100_000, "ki_trend": 80_000, "fair_value": 2_000_000}}
    if own:
        p.update(uoid="me", uop=1_000_000)
    p.update(changes)
    return p


class BaseXiTests(unittest.TestCase):
    def test_real_schema_cache_and_no_credential_transmission(self):
        session = Mock()
        session.get.return_value.json.return_value = [ROW]
        with tempfile.TemporaryDirectory() as folder:
            first = fetch_base_xi(folder, {}, session, now=100000)
            second = fetch_base_xi(folder, {}, session, now=100010)
            self.assertTrue(second["available"])
            self.assertEqual(session.get.call_count, 1)
            session.get.assert_called_once_with("https://www.base-xi.de/api/players", params={"comp": "1"}, timeout=20)
            p = enrich_base_xi([{"i": "7226", "prob": 4, "mv": 65_000_000, "uop": 42}], first)[0]
            self.assertEqual(p["prob"], 4)  # starts=2 is NOT S11 probability
            self.assertEqual(p["mv"], 65_000_000)
            self.assertEqual(p["uop"], 42)
            self.assertEqual(p["base_xi"]["starts"], 2)
            self.assertEqual(p["base_xi"]["median_source"], "vorsaison")
            self.assertEqual(p["performance"]["average_points"], 134)

    def test_failure_backoff_stale_and_disabled(self):
        session = Mock()
        session.get.return_value.json.return_value = [ROW]
        with tempfile.TemporaryDirectory() as folder:
            fetch_base_xi(folder, {}, session, now=100000)
            session.get.side_effect = requests.HTTPError("429")
            bad = fetch_base_xi(folder, {}, session, now=130000)
            self.assertFalse(bad["available"])
            fetch_base_xi(folder, {}, session, now=130100)
            self.assertEqual(session.get.call_count, 2)
            self.assertFalse(fetch_base_xi(folder, {"base_xi_enabled": False}, session)["available"])

    def test_detail_ids_are_matched_and_cached(self):
        session = Mock()
        session.get.return_value.json.return_value = {"success": True, "data": {"id": "7226", "form": [{"day": 3, "points": 209, "season": "26/27"}]}}
        source = {"available": True, "players": {"7226": dict(ROW)}}
        with tempfile.TemporaryDirectory() as folder:
            result = fetch_base_xi_forms(source, [{"i": "7226"}], folder, {}, session, now=100000)
            fetch_base_xi_forms(source, [{"i": "7226"}], folder, {}, session, now=100100)
            self.assertEqual(session.get.call_count, 1)
            self.assertEqual(result["players"]["7226"]["detail_form"][0]["points"], 209)


class BidPolicyTests(unittest.TestCase):
    def test_own_offer_identity_never_incoming_or_another_manager(self):
        self.assertIsNone(own_offer(candidate(uoid="other", uop=10), "me"))
        self.assertIsNone(own_offer(candidate(own=True, u={"i": "me"}), "me"))
        self.assertIsNone(own_offer(candidate(ofs=[{"price": 100}]), "me"))
        self.assertEqual(own_offer(candidate(ofs=[{"u": "me", "uop": 100}]), "me")["offer_id"], "me")
        self.assertEqual(login_user_id({"u": {"i": "me"}}), "me")

    def test_injury_withdraws_own_bid_and_blocks_rebuy(self):
        p = candidate(own=True, st=2)
        plan = plan_bids([p], [], {}, "me", 10_000_000)
        self.assertEqual([a["kind"] for a in plan["actions"]], ["withdraw_bid"])
        self.assertEqual(plan["actions"][0]["offer_id"], "me")

    def test_falling_trade_and_excessive_bid_are_withdrawn(self):
        p = candidate(own=True)
        p["base_xi"]["trend_24h"] = -100
        plan = plan_bids([p], [], {}, "me", 10_000_000, {"10": {"purpose": "trading"}})
        self.assertEqual(plan["actions"][0]["kind"], "withdraw_bid")
        p = candidate(own=True, uop=1_300_000)
        self.assertEqual(plan_bids([p], [], {}, "me", 10_000_000)["actions"][0]["kind"], "withdraw_bid")

    def test_source_outage_does_not_mass_cancel_but_blocks_new_bids(self):
        p = candidate(own=True)
        p["base_xi"] = {"available": False}
        plan = plan_bids([p], [], {}, "me", 10_000_000)
        self.assertEqual(plan["actions"], [])
        self.assertTrue(plan["blocked"])

    def test_no_minutes_can_only_be_small_explicit_trading_position(self):
        p = candidate()
        p["base_xi"].update(matches=0, average_minutes=0, average_points=0)
        result = assess(p, {})
        self.assertEqual(result["purpose"], "trading")
        self.assertTrue(result["eligible"])
        p["base_xi"]["trend_24h"] = -100
        self.assertFalse(assess(p, {})["eligible"])
        p["base_xi"]["trend_24h"] = 100000
        p["mv"] = p["prc"] = 4_000_000
        self.assertFalse(assess(p, {})["eligible"])

    def test_identical_live_bid_not_repeated_and_unknown_budget_no_buy(self):
        p = candidate(own=True)
        self.assertEqual(plan_bids([p], [], {}, "me", 10_000_000)["actions"], [])
        self.assertEqual(plan_bids([candidate()], [], {}, "me", None)["actions"], [])
        self.assertEqual(plan_bids([candidate()], [], {"auto_buy": False}, "me", 10_000_000)["actions"], [])

    def test_budget_counts_all_existing_bids_and_no_expected_sale_cash(self):
        players = [candidate("10", own=True), candidate("11", own=True, pos=4), candidate("12", pos=2)]
        plan = plan_bids(players, [], {}, "me", 2_500_000)
        self.assertEqual([a["kind"] for a in plan["actions"]], ["withdraw_bid"])
        players = [candidate("10"), candidate("11", pos=4)]
        plan = plan_bids(players, [], {}, "me", 2_500_000)
        self.assertLessEqual(sum(a["amount"] for a in plan["actions"]), 1_500_000)

    def test_disabling_withdraw_keeps_existing_bid_and_no_new_exposure(self):
        p = candidate(own=True, st=2)
        plan = plan_bids([p, candidate("20")], [], {"auto_withdraw_bids": False}, "me", 2_000_000)
        self.assertEqual(plan["actions"], [])


class ExecutionTests(unittest.TestCase):
    def test_api_error_in_success_http_response_is_rejected(self):
        client = app.KickbaseClient()
        response = Mock(status_code=200)
        response.json.return_value = {"errMsg": "NotFound"}
        client.session = Mock()
        client.session.request.return_value = response
        with self.assertRaisesRegex(ValueError, "abgelehnt"):
            client.write("POST", "/test", {})

    def test_listing_and_acceptance_use_distinct_correct_endpoints(self):
        p = candidate()
        for kind in ("list", "adjust_price", "accept_offer"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                action = {"kind": kind, "player": p, "amount": 1_000_000,
                          "offer": {"u": {"i": "bidder"}}, "reason": "Test"}
                plan = {"actions": [action], "blocked": [], "lineup": {}}
                client = Mock()
                with patch.object(app, "build_trade_plan", return_value=plan):
                    result = self.run_plan(client, folder, True, candidate(st=2))
                self.assertTrue(result["actions"][0]["ok"])
                if kind == "accept_offer":
                    client.write.assert_called_once_with("DELETE", "/v4/leagues/league/market/10/offers/bidder/accept")
                else:
                    client.write.assert_called_once_with("POST", "/v4/leagues/league/market/",
                        {"pi": "10", "prc": 1_000_000, "playerId": "10", "price": 1_000_000})

    def run_plan(self, client, folder, live, p):
        with patch.object(app, "DATA", Path(folder)):
            return app.run_trading(client, "league", [p], {"me": {"budget": 10_000_000}},
                                   {"mode": "live" if live else "observe", "trading_enabled": live}, {}, "me")

    def test_observe_no_delete_live_exact_delete_and_no_sell(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as folder:
            observed = self.run_plan(client, folder, False, candidate(own=True, st=2))
            client.write.assert_not_called()
            self.assertEqual(observed["planned"][0]["action"], "withdraw_bid")
            executed = self.run_plan(client, folder, True, candidate(own=True, st=2))
            client.write.assert_called_once_with("DELETE", "/v4/leagues/league/market/10/offers/me")
            self.assertTrue(executed["actions"][0]["ok"])

    def test_failed_withdraw_is_not_logged_as_success_and_retries(self):
        client = Mock()
        client.write.side_effect = requests.HTTPError("503")
        with tempfile.TemporaryDirectory() as folder:
            first = self.run_plan(client, folder, True, candidate(own=True, st=2))
            self.assertFalse(first["actions"][0]["ok"])
            client.write.side_effect = None
            second = self.run_plan(client, folder, True, candidate(own=True, st=2))
            self.assertTrue(second["actions"][0]["ok"])
            self.assertEqual(client.write.call_count, 2)


class DigestTests(unittest.TestCase):
    def test_hourly_queue_deduplication_and_restart(self):
        sender = Mock(return_value={"sent": True})
        config = {"email_notifications": True, "email_digest_minutes": 5}
        event = {"id": "blocked:10", "text": "Spieler blockiert"}
        with tempfile.TemporaryDirectory() as folder:
            for t in range(0, 3600, 300):
                result = hourly_digest(folder, config, [event], sender, now=100000 + t)
                self.assertFalse(result["sent"])
            result = hourly_digest(folder, config, [], sender, now=103600)
            self.assertTrue(result["sent"])
            self.assertEqual(sender.call_count, 1)
            self.assertEqual(sender.call_args.args[2].count("Spieler blockiert"), 1)
            hourly_digest(folder, config, [event, {"id": "trade:1", "text": "Verkauft"}], sender, now=103900)
            self.assertEqual(sender.call_count, 1)
            hourly_digest(folder, config, [], sender, now=107200)
            self.assertEqual(sender.call_count, 2)
            self.assertIn("Verkauft", sender.call_args.args[2])

    def test_failed_smtp_keeps_events_and_retries_only_next_hour(self):
        sender = Mock(return_value={"sent": False, "reason": "SMTP Fehler"})
        config = {"email_notifications": True}
        event = {"id": "trade:1", "text": "Gebot zurückgezogen"}
        with tempfile.TemporaryDirectory() as folder:
            hourly_digest(folder, config, [event], sender, now=100000)
            hourly_digest(folder, config, [], sender, now=103600)
            hourly_digest(folder, config, [], sender, now=103900)
            self.assertEqual(sender.call_count, 1)
            self.assertEqual(len(read_cache(Path(folder) / "email_digest.json")["pending"]), 1)
            sender.return_value = {"sent": True}
            hourly_digest(folder, config, [], sender, now=107200)
            self.assertEqual(sender.call_count, 2)

    def test_disabled_does_not_send(self):
        sender = Mock()
        with tempfile.TemporaryDirectory() as folder:
            hourly_digest(folder, {}, [{"id": "x", "text": "x"}], sender, now=100000)
            sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()

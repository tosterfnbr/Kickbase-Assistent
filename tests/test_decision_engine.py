import unittest

from decision_engine import (
    best_lineup,
    build_trade_plan,
    enrich_s11,
    price_limits,
    s11_score,
    selling_candidates,
)


def player(pid, pos, score=None, mv=1_000_000, trend=0, points=50, owner=""):
    item = {"id": str(pid), "fn": "Test", "n": f"Spieler{pid}", "pos": pos, "mv": mv, "mvt": trend, "ap": points}
    if score is not None:
        item["prob"] = score
    if owner:
        item["u"] = owner
    return item


class DecisionEngineTests(unittest.TestCase):
    def squad(self):
        return [
            player("g1", 1, 5), player("g2", 1, None),
            *[player(f"d{i}", 2, 5 if i < 4 else 2, points=60-i) for i in range(6)],
            *[player(f"m{i}", 3, 5 if i < 5 else 2, points=70-i) for i in range(7)],
            *[player(f"f{i}", 4, 5 if i < 3 else 2, points=80-i) for i in range(4)],
        ]

    def test_unknown_is_not_zero(self):
        self.assertIsNone(s11_score(player("x", 2, None)))

    def test_ligainsider_overrides_kickbase(self):
        raw = player("x", 2, 2)
        raw["fn"], raw["n"] = "Max", "Muster"
        enriched = enrich_s11([raw], {"players": {"max muster": {"score": 5, "status": "voraussichtliche Startelf"}}})[0]
        self.assertEqual(enriched["s11"]["score"], 5)
        self.assertEqual(enriched["s11"]["source"], "LigaInsider")
        self.assertEqual(enriched["s11"]["kickbase"], 2)

    def test_best_lineup_is_valid_and_complete(self):
        result = best_lineup(self.squad())
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["players"]), 11)
        counts = {pos: sum(p["pos"] == pos for p in result["players"]) for pos in range(1, 5)}
        self.assertEqual(counts[1], 1)
        self.assertEqual(sum(counts.values()), 11)

    def test_unknown_s11_can_be_listed_but_never_instant_sold(self):
        squad = self.squad()
        candidates = selling_candidates(squad, {"minimum_starting_probability": 3, "auto_instant_sell": True, "list_all_players": True})
        unknown = next(item for item in candidates if item["player_id"] == "g2")
        self.assertEqual(unknown["method"], "list")
        self.assertNotIn("S11", unknown["reason"])

    def test_good_offer_wins_before_price_adjustment(self):
        listed = player("sale", 2, 2, mv=10_000_000, owner="me")
        listed.update({"prc": 10_500_000, "offers": [{"id": "offer", "prc": 9_900_000}]})
        plan = build_trade_plan([listed], self.squad() + [listed], {"minimum_offer_percent": 98, "auto_accept_offers": True, "auto_adjust_listings": True}, "me")
        action = next(item for item in plan["actions"] if item["player_id"] == "sale")
        self.assertEqual(action["kind"], "accept_offer")

    def test_dynamic_price_rewards_rising_safe_starter(self):
        strong = player("x", 3, 5, mv=10_000_000, trend=2)
        limits = price_limits(strong, {"asking_price_percent": 2, "rising_price_bonus_percent": 3, "safe_s11_price_bonus_percent": 2})
        self.assertEqual(limits["asking"], 10_700_000)


    def test_portfolio_lists_core_and_reserve_players(self):
        squad = self.squad()
        plan = build_trade_plan([], squad, {"portfolio_mode": True, "list_all_players": True}, "me", False, 0)
        listed = [item for item in plan["actions"] if item["kind"] == "list"]
        self.assertEqual(len(listed), len(squad))
        self.assertTrue(any(item["is_core"] for item in listed))
        self.assertTrue(any(not item["is_core"] for item in listed))
        self.assertTrue(all(isinstance(item.get("amount"), int) and item["amount"] > 0 for item in listed))

    def test_continuous_bidding_ignores_expiry_window(self):
        squad = self.squad()
        candidate = player("upgrade", 3, 5, mv=1_000_000, points=500)
        candidate.update({"prc": 1_000_000, "exs": 6 * 60 * 60})
        plan = build_trade_plan(
            [candidate], squad,
            {"continuous_bidding": True, "bid_window_minutes": 10, "minimum_cash": 1_000_000},
            "me", False, 10_000_000,
        )
        self.assertTrue(any(item["kind"] == "buy" and item["player_id"] == "upgrade" for item in plan["actions"]))

    def test_late_only_bidding_still_respects_expiry_window(self):
        squad = self.squad()
        candidate = player("upgrade", 3, 5, mv=1_000_000, points=500)
        candidate.update({"prc": 1_000_000, "exs": 6 * 60 * 60})
        plan = build_trade_plan(
            [candidate], squad,
            {"continuous_bidding": False, "bid_window_minutes": 10, "minimum_cash": 1_000_000},
            "me", False, 10_000_000,
        )
        self.assertFalse(any(item["kind"] == "buy" for item in plan["actions"]))

    def test_purchase_price_and_star_profit_protect_offer_floor(self):
        star = player("star", 3, 5, mv=10_000_000, trend=2)
        star["purchasePrice"] = 12_000_000
        limits = price_limits(star, {"target_profit_percent": 5, "star_sale_profit_percent": 10}, is_core=True)
        self.assertGreaterEqual(limits["accept"], 13_200_000)

    def test_multiple_good_offers_cannot_sell_below_eleven(self):
        squad = best_lineup(self.squad())["players"] + [player("reserve", 3, 3)]
        market = []
        for p in squad:
            market.append({**p, "u": "me", "prc": 1_000_000,
                           "offers": [{"id": "bidder", "prc": 3_000_000}]})
        plan = build_trade_plan(market, squad, {"auto_buy": False}, "me")
        sales = [a for a in plan["actions"] if a["kind"] == "accept_offer"]
        self.assertEqual(len(sales), 1)
        remaining = [p for p in squad if p["id"] != sales[0]["player_id"]]
        self.assertTrue(best_lineup(remaining)["complete"])

if __name__ == "__main__":
    unittest.main()

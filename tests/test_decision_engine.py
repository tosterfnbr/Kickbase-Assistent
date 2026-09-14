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

    def test_unknown_s11_is_never_auto_sell_reason(self):
        squad = self.squad()
        candidates = selling_candidates(squad, {"minimum_starting_probability": 3, "auto_instant_sell": True})
        candidate_ids = {item["player_id"] for item in candidates}
        self.assertNotIn("g2", candidate_ids)

    def test_good_offer_wins_before_price_adjustment(self):
        listed = player("sale", 2, 2, mv=10_000_000, owner="me")
        listed.update({"prc": 10_500_000, "offers": [{"id": "offer", "prc": 9_900_000}]})
        plan = build_trade_plan([listed], self.squad(), {"minimum_offer_percent": 98, "auto_accept_offers": True, "auto_adjust_listings": True}, "me")
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

    def test_purchase_price_and_star_profit_protect_offer_floor(self):
        star = player("star", 3, 5, mv=10_000_000, trend=2)
        star["purchasePrice"] = 12_000_000
        limits = price_limits(star, {"target_profit_percent": 5, "star_sale_profit_percent": 10}, is_core=True)
        self.assertGreaterEqual(limits["accept"], 13_200_000)

if __name__ == "__main__":
    unittest.main()

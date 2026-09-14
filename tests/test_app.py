import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_optional(self, *paths):
        self.calls.append(paths)
        return {
            "ok": True,
            "path": paths[0],
            "data": {"i": "p1", "fn": "Max", "ln": "Muster", "pos": 3, "mv": 12_345_678, "ap": 88},
        }


class PlayerDetailTests(unittest.TestCase):
    def test_missing_squad_value_is_loaded_and_cached(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "DATA", Path(folder)):
            first = app.hydrate_squad_details(
                client, "league", [{"i": "p1", "fn": "Max", "n": "Muster", "pos": 3}],
                {"player_details_refresh_minutes": 60},
            )
            second = app.hydrate_squad_details(
                client, "league", [{"i": "p1", "fn": "Max", "n": "Muster", "pos": 3}],
                {"player_details_refresh_minutes": 60},
            )
        self.assertEqual(first[0]["mv"], 12_345_678)
        self.assertEqual(second[0]["ap"], 88)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], "/v4/leagues/league/players/p1")


if __name__ == "__main__":
    unittest.main()

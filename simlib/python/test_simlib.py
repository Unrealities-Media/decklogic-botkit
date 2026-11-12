"""Runs against a built library: set DECKLOGIC_SIMLIB_DIR (or DECKLOGIC_SIMLIB)
and optionally DECKLOGIC_SIMLIB_PACK (default: the HOB pack of the DeckLogic
checkout this file sits in). Skipped, and says so, when no library is set."""

import os
import unittest

import simlib

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("DECKLOGIC_SIMLIB_PACK", os.path.join(HERE, "..", "..", "..", "etl", "sim", "sim_HOB.json.gz"))
CONFIGURED = bool(os.environ.get("DECKLOGIC_SIMLIB") or os.environ.get("DECKLOGIC_SIMLIB_DIR"))


@unittest.skipUnless(CONFIGURED, "set DECKLOGIC_SIMLIB_DIR to the directory holding the built library")
class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.lib = simlib.Library.from_env()
        self.engine = self.lib.engine(PACK)
        self.decks = self.engine.decks()

    def play(self, seed):
        game = self.engine.game([self.decks[0]["main"], self.decks[1]["main"]], seed=seed, labels=False)
        bots = [game.bot("random", seat, seed) for seat in (0, 1)]
        ids = []
        while True:
            d = game.decision()
            if d["type"] == "over":
                return ids, d["result"]
            self.assertEqual(game.seat(), d["seat"])
            self.assertNotIn("label", d["actions"][0])
            action_id = bots[d["seat"]].choose()
            game.apply(action_id)
            ids.append(action_id)

    def test_info_and_cards(self):
        self.assertEqual(self.lib.info["library"], simlib.LIBRARY)
        self.assertEqual(self.lib.info["protocol"], "decklogic-bot/1")
        self.assertEqual(self.engine.cards()["format"], "decklogic-cards/1")

    def test_a_game_plays_to_the_end_and_repeats(self):
        first = self.play(3)
        self.assertGreater(len(first[0]), 20)
        self.assertEqual(first, self.play(3))

    def test_errors_carry_the_library_message(self):
        with self.assertRaises(simlib.SimlibError) as missing:
            self.lib.engine("/no/such/pack.json")
        self.assertIn("/no/such/pack.json", str(missing.exception))
        game = self.engine.game([self.decks[0]["main"], self.decks[1]["main"]], seed=1)
        with self.assertRaises(simlib.SimlibError) as refused:
            game.apply(9999)
        self.assertIn("not offered", str(refused.exception))
        with self.assertRaises(simlib.SimlibError):
            game.bot("grandmaster", 0, 1)
        self.assertTrue(game.bot("deep", 1, 1).version)


if __name__ == "__main__":
    unittest.main()

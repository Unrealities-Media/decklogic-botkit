"""Runs against a built library, like test_simlib.py."""

import os
import tempfile
import unittest

import simlib
import simlib_traces

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("DECKLOGIC_SIMLIB_PACK", os.path.join(HERE, "..", "..", "..", "etl", "sim", "sim_HOB.json.gz"))
CONFIGURED = bool(os.environ.get("DECKLOGIC_SIMLIB") or os.environ.get("DECKLOGIC_SIMLIB_DIR"))


@unittest.skipUnless(CONFIGURED, "set DECKLOGIC_SIMLIB_DIR to the directory holding the built library")
class TraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = simlib.Library.from_env()
        cls.engine = cls.lib.engine(PACK)

    def test_a_game_is_header_steps_and_result(self):
        records = list(simlib_traces.record(self.engine, ("quick", "random"), seed=4))
        game, steps, over = records[0], records[1:-1], records[-1]
        self.assertEqual(game["type"], "game")
        self.assertEqual(game["schema"], simlib_traces.SCHEMA)
        self.assertEqual([p["bot"] for p in game["players"]], ["quick", "random"])
        self.assertTrue(all(p["version"] for p in game["players"]))
        self.assertEqual(over["type"], "over")
        self.assertEqual(over["steps"], len(steps))
        for i, s in enumerate(steps):
            self.assertEqual(s["n"], i)
            self.assertEqual(s["seat"], s["decision"]["seat"])
            self.assertEqual(s["decision"]["actions"][s["chosen_index"]]["id"], s["chosen"])
            self.assertTrue(all("label" not in a for a in s["decision"]["actions"]))

    def test_a_seed_records_the_same_game(self):
        a = list(simlib_traces.record(self.engine, ("deep", "quick"), seed=8))
        b = list(simlib_traces.record(self.engine, ("deep", "quick"), seed=8))
        self.assertEqual(a, b)

    def test_the_command_writes_a_file_read_gives_back(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "t.jsonl.gz")
            self.assertEqual(simlib_traces.main(["--pack", PACK, "--a", "random", "--b", "random",
                                                 "--games", "2", "--out", out]), 0)
            records = list(simlib_traces.read(out))
        games = [r for r in records if r["type"] == "game"]
        self.assertEqual(len(games), 2)
        self.assertEqual([g["seed"] for g in games], [1, 2])
        for g in games:
            self.assertEqual(g["engine"], self.lib.info["engine"])
            self.assertEqual(len(g["pack_sha256"]), 64)
        self.assertEqual(sum(r["type"] == "over" for r in records), 2)


if __name__ == "__main__":
    unittest.main()

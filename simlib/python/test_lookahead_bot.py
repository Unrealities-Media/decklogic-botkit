"""Runs against a built library, like test_simlib (same environment variables)."""

import unittest

import simlib
from test_simlib import CONFIGURED, PACK


@unittest.skipUnless(CONFIGURED, "set DECKLOGIC_SIMLIB_DIR to the directory holding the built library")
class LookaheadTests(unittest.TestCase):
    def test_a_look_ahead_game_plays_to_the_end_on_samples(self):
        import lookahead_bot

        lib = simlib.Library.from_env()
        if getattr(lib._dll, "dls_game_sample", None) is None:
            self.skipTest("this library predates dls_game_sample")
        engine = lib.engine(PACK)
        decks = engine.decks()
        game = engine.game([decks[0]["main"], decks[1]["main"]], seed=2, labels=False)
        bot = lookahead_bot.LookaheadBot(game, 0, 2, worlds=1, candidates=2, rollout="random")
        opponent = game.bot("random", seat=1, seed=2)
        while (seat := game.seat()) is not None:
            d = game.decision()
            game.apply(bot.choose(game, d) if seat == 0 else opponent.choose())
        self.assertEqual(game.decision()["type"], "over")
        self.assertGreater(bot.stats["searched"], 0)
        self.assertGreater(bot.stats["rollouts"], bot.stats["searched"])


if __name__ == "__main__":
    unittest.main()

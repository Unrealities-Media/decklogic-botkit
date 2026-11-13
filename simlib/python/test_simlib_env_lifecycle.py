"""Lifecycle failure injection; no native library required."""
import unittest
from unittest.mock import Mock
import simlib_env


class LifecycleTests(unittest.TestCase):
    def game(self):
        game = Mock()
        game.decision.return_value = {"type": "decision", "seat": 0, "actions": [{"id": 1}]}
        return game

    def inactive(self, env):
        self.assertIsNone(env.table.game)
        self.assertIsNone(env.table.decision)
        self.assertEqual(env.table.cut, 0)
        with self.assertRaisesRegex(RuntimeError, "reset"):
            env.step(0)
        if isinstance(env, simlib_env.SimlibAEC):
            self.assertEqual(env.agents, [])
            with self.assertRaisesRegex(RuntimeError, "reset"):
                env.last()
            with self.assertRaisesRegex(RuntimeError, "reset"):
                env.observe("seat_0")

    def test_inactive_close_and_recovery(self):
        for cls in (simlib_env.SimlibEnv, simlib_env.SimlibAEC):
            engine = Mock(); game = self.game(); engine.game.return_value = game
            env = cls(engine, decks=[[1]], **({"seat": 0} if cls is simlib_env.SimlibEnv else {}))
            self.inactive(env)
            env.reset(seed=1)
            env.close(); env.close()
            self.inactive(env)
            game.close.assert_called_once()
            env.reset(seed=2)
            self.assertIs(env.table.game, game)
            env.close()

    def test_failed_game_or_decision_creation_invalidates_episode(self):
        for cls in (simlib_env.SimlibEnv, simlib_env.SimlibAEC):
            for failure in ('game', 'decision'):
                engine = Mock(); old = self.game(); new = self.game()
                engine.game.return_value = old
                env = cls(engine, decks=[[1]], **({"seat": 0} if cls is simlib_env.SimlibEnv else {}))
                env.reset(seed=1)
                engine.game.return_value = new
                (engine.game if failure == 'game' else new.decision).side_effect = ValueError('injected')
                with self.assertRaisesRegex(ValueError, 'injected'):
                    env.reset(seed=2)
                old.close.assert_called_once()
                if failure == 'decision':
                    new.close.assert_called_once()
                self.inactive(env)
                if isinstance(env, simlib_env.SimlibEnv):
                    self.assertEqual(env.games, 1)

    def test_opponent_creation_and_advance_failure_cleanup_and_seat_retry(self):
        for failure in ('bot', 'advance'):
            engine = Mock(); game = self.game(); engine.game.return_value = game
            env = simlib_env.SimlibEnv(engine, decks=[[1]])
            if failure == 'bot':
                game.bot.side_effect = ValueError('injected')
            else:
                game.decision.return_value['seat'] = 1
                game.bot.return_value.choose.side_effect = ValueError('injected')
            with self.assertRaisesRegex(ValueError, 'injected'):
                env.reset(seed=1)
            game.close.assert_called_once()
            if failure == 'advance':
                game.bot.return_value.close.assert_called_once()
            self.inactive(env)
            self.assertEqual(env.games, 0)
            good = self.game(); engine.game.return_value = good
            _, info = env.reset(seed=2)
            self.assertEqual(info['seat'], 0)
            self.assertEqual(env.games, 1)
            env.close()


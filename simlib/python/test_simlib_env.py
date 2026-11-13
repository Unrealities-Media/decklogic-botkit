"""Runs against a built library, like test_simlib.py: set DECKLOGIC_SIMLIB_DIR
(or DECKLOGIC_SIMLIB) and optionally DECKLOGIC_SIMLIB_PACK."""

import os
import random
import unittest

import simlib
import simlib_env

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("DECKLOGIC_SIMLIB_PACK", os.path.join(HERE, "..", "..", "..", "etl", "sim", "sim_HOB.json.gz"))
CONFIGURED = bool(os.environ.get("DECKLOGIC_SIMLIB") or os.environ.get("DECKLOGIC_SIMLIB_DIR"))


def masked_choice(rng, mask):
    return rng.choice([i for i, m in enumerate(mask) if m])


@unittest.skipUnless(CONFIGURED, "set DECKLOGIC_SIMLIB_DIR to the directory holding the built library")
class EnvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = simlib.Library.from_env()
        cls.engine = cls.lib.engine(PACK)

    def episode(self, env, seed):
        rng = random.Random(seed)
        obs, info = env.reset(seed=seed)
        steps, total = 0, 0.0
        while True:
            d = obs["decision"]
            self.assertEqual(d["type"], "decision")
            self.assertEqual(d["seat"], info["seat"])
            self.assertEqual(sum(obs["action_mask"]), min(len(d["actions"]), env.max_actions))
            obs, reward, terminated, truncated, info = env.step(masked_choice(rng, obs["action_mask"]))
            total += reward
            steps += 1
            self.assertFalse(terminated and truncated)
            if terminated or truncated:
                self.assertEqual(truncated, obs["decision"]["result"] == "capped")
                self.assertEqual(obs["decision"]["type"], "over")
                self.assertEqual(sum(obs["action_mask"]), 0)
                self.assertIn(reward, (-1.0, 0.0, 1.0))
                return steps, total, info

    def test_single_agent_episodes_end_with_the_seat_result(self):
        env = simlib_env.SimlibEnv(self.engine, opponent="random")
        seats = []
        for seed in range(4):
            steps, total, info = self.episode(env, seed)
            self.assertGreater(steps, 0)
            winner = info["result"].get("winner")
            self.assertEqual(total, 0.0 if winner is None else (1.0 if winner == info["seat"] else -1.0))
            seats.append(info["seat"])
        self.assertEqual(seats, [0, 1, 0, 1])
        env.close()

    def test_a_seed_replays_the_same_game(self):
        env = simlib_env.SimlibEnv(self.engine, opponent="quick", seat=1)
        self.assertEqual(self.episode(env, 9), self.episode(env, 9))
        env.close()

    def test_an_index_that_is_not_offered_is_refused(self):
        env = simlib_env.SimlibEnv(self.engine, opponent="random", seat=0)
        obs, _ = env.reset(seed=3)
        with self.assertRaises(ValueError):
            env.step(sum(obs["action_mask"]))
        env.close()

    def test_a_short_mask_keeps_every_kept_action_legal(self):
        env = simlib_env.SimlibEnv(self.engine, opponent="random", seat=0, max_actions=2)
        _, _, info = self.episode(env, 5)
        self.assertGreater(info["actions_cut"], 0)
        env.close()

    def test_lifecycle_failure_close_and_recovery(self):
        for cls in (simlib_env.SimlibEnv, simlib_env.SimlibAEC):
            env = cls(self.engine)
            env.reset(seed=1)
            with self.assertRaises(IndexError):
                env.reset(seed=2, options={"decks": ([],)})
            with self.assertRaisesRegex(RuntimeError, "reset"):
                env.step(0)
            if isinstance(env, simlib_env.SimlibEnv):
                self.assertEqual(env.games, 1)
            env.reset(seed=3)
            env.close()
            env.close()
            with self.assertRaisesRegex(RuntimeError, "reset"):
                env.step(0)
            if isinstance(env, simlib_env.SimlibAEC):
                with self.assertRaisesRegex(RuntimeError, "reset"):
                    env.last()
                with self.assertRaisesRegex(RuntimeError, "reset"):
                    env.observe("seat_0")
            env.reset(seed=4)
            env.close()

    def test_self_play_follows_the_aec_protocol(self):
        env = simlib_env.SimlibAEC(self.engine)
        env.reset(seed=11)
        rng = random.Random(11)
        acted = {"seat_0": 0, "seat_1": 0}
        finals = {}
        for agent in env.agent_iter():
            obs, reward, terminated, truncated, info = env.last()
            if terminated or truncated:
                finals[agent] = reward
                env.step(None)
                continue
            self.assertEqual(obs["decision"]["seat"], env.possible_agents.index(agent))
            other = env.possible_agents[1 - env.possible_agents.index(agent)]
            self.assertIsNone(env.observe(other)["decision"])
            acted[agent] += 1
            env.step(masked_choice(rng, obs["action_mask"]))
        self.assertEqual(env.agents, [])
        with self.assertRaisesRegex(RuntimeError, "reset"):
            env.last()
        with self.assertRaisesRegex(RuntimeError, "reset"):
            env.step(None)
        self.assertEqual(env.observe("seat_0")["decision"]["type"], "over")
        self.assertTrue(all(acted.values()))
        self.assertEqual(sorted(finals), ["seat_0", "seat_1"])
        self.assertEqual(finals["seat_0"], -finals["seat_1"])
        env.close()


if __name__ == "__main__":
    unittest.main()

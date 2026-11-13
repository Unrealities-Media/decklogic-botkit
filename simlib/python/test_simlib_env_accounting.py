"""Pure environment diagnostics; no engine binary or card pack required."""
import unittest

import simlib_env


class ObservationAccountingTests(unittest.TestCase):
    def test_repeated_and_inactive_reads_do_not_inflate_cut_decisions(self):
        env = simlib_env.SimlibAEC(None, decks=[[1]], max_actions=1)
        env.table.decision = {"type": "decision", "seat": 0,
                              "actions": [{"id": 0}, {"id": 1}]}
        inactive = env.observe("seat_1")
        self.assertIsNone(inactive["decision"])
        self.assertEqual(env.table.cut, 0)
        first = env.observe("seat_0")
        self.assertEqual(env.table.cut, 1)
        self.assertEqual(env.observe("seat_0"), first)
        self.assertEqual(env.table.cut, 1)
        # A distinct engine decision is a second cut even with identical offers.
        env.table.decision = dict(env.table.decision)
        env.observe("seat_0")
        self.assertEqual(env.table.cut, 2)


if __name__ == "__main__":
    unittest.main()

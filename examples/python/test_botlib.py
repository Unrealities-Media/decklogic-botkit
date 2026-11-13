"""Client tests: replay the recorded golden transcript and a probe-style decision.

    python -m unittest test_botlib    (from examples/python)
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

import botlib
import random_bot
import simple_bot

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "..", "..", "protocol", "golden-transcript.txt")
SYNTHETIC = os.path.join(HERE, "..", "..", "protocol", "synthetic-transcript.txt")


def host_lines(path=None):
    # Public distributions carry a hand-authored, data-free fixture. Keep the
    # private recorded game when available; also test synthetic explicitly below.
    with open(path or (GOLDEN if os.path.exists(GOLDEN) else SYNTHETIC), encoding="utf-8") as f:
        return [line[2:] for line in f if line.startswith("> ")]


def play(bot, lines):
    out = io.StringIO()
    with redirect_stdout(out):
        botlib.run(bot, lines)
    return [json.loads(l) for l in out.getvalue().splitlines()]


class GoldenTranscript(unittest.TestCase):
    def test_public_synthetic_fixture_answers_every_decision(self):
        lines = host_lines(SYNTHETIC)
        decisions = [json.loads(line) for line in lines if json.loads(line)["type"] == "decision"]
        self.assertGreaterEqual(len(decisions), 3)
        for bot in (random_bot.RandomBot(), simple_bot.SimpleBot()):
            replies = play(bot, lines)
            actions = [reply for reply in replies if reply["type"] == "action"]
            self.assertEqual(len(actions), len(decisions))
            for decision, answer in zip(decisions, actions):
                self.assertEqual(answer["n"], decision["n"])
                self.assertIn(answer["id"], [action["id"] for action in decision["actions"]])

    def test_every_example_answers_every_decision_with_an_offered_id(self):
        lines = host_lines()
        decisions = [json.loads(l) for l in lines if json.loads(l)["type"] == "decision"]
        for bot in (random_bot.RandomBot(), simple_bot.SimpleBot()):
            replies = play(bot, lines)
            self.assertEqual(replies[0]["type"], "ready")
            self.assertEqual(replies[0]["protocol"], botlib.PROTOCOL)
            actions = [r for r in replies if r["type"] == "action"]
            self.assertEqual(len(actions), len(decisions))
            for d, a in zip(decisions, actions):
                self.assertEqual(a["n"], d["n"])
                self.assertIn(a["id"], [x["id"] for x in d["actions"]])

    def test_the_legacy_signature_still_works(self):
        class Old(botlib.Bot):
            def choose(self, observation, question, actions):
                return actions[-1]["id"]

        replies = play(Old(), host_lines())
        self.assertTrue(all(isinstance(r["id"], int) for r in replies if r["type"] == "action"))


class ForwardCompatible(unittest.TestCase):
    def test_unknown_messages_fields_kinds_and_cards_never_raise(self):
        sheet = {"cards": [{"grp_ids": [1], "name": "Known", "mana_value": 2}], "keyword_bits": [{"bit": 0, "name": "flying"}]}
        lines = [
            json.dumps({"type": "hello", "protocol": botlib.PROTOCOL, "engine": "e", "abi": 1, "cards": sheet,
                        "limits": {"decision_ms": 250}, "x_new": 1}),
            json.dumps({"type": "x_future_message", "anything": [1, 2]}),
            json.dumps({"type": "game_start", "game": 0, "seat": 0, "on_play": True, "seed": 3, "deck": [1]}),
            json.dumps({"type": "decision", "n": 4, "x_new": {}, "question": {"kind": "priority", "x_new": 1},
                        "observation": {"seat": 0, "hand": [{"id": 9, "grp_id": 999, "keywords": 1, "x_new": 1}], "x_new": 1},
                        "actions": [
                            {"id": 0, "label": "?", "action": {"action": "x_probe_future_kind", "x_new": 1}},
                            {"id": 1, "label": "?", "action": {"action": "cast", "card": 9, "x_new": 1}},
                            {"id": 2, "label": "?", "action": {"action": "pass"}},
                        ]}),
            json.dumps({"type": "bye"}),
        ]
        bot = simple_bot.SimpleBot()
        replies = play(bot, lines)
        self.assertEqual(bot.limits.decision_ms, 250)
        self.assertEqual([r["type"] for r in replies], ["ready", "action"])
        self.assertEqual(replies[1]["n"], 4)
        self.assertEqual(replies[1]["id"], 1, "an unknown card still casts; the unknown kind scores low")
        self.assertIsNone(bot.cards.of({"grp_id": 999}))
        self.assertEqual(bot.cards.text({"grp_id": 1}), "", "absent text reads as empty, never a KeyError")
        self.assertIsNone(bot.cards.ability({"grp_id": 999}, 0))
        self.assertEqual(bot.cards.name({"grp_id": 1}), "Known")
        self.assertTrue(bot.cards.has_keyword({"keywords": 1}, "flying"))
        self.assertFalse(bot.cards.has_keyword({"keywords": 1}, "a_keyword_this_sheet_lacks"))

    def test_searched_cards_and_named_counters_are_readable(self):
        decision = botlib.Decision({
            "n": 1,
            "question": {"kind": "pick", "context": 40, "purpose": "tutor_to_hand"},
            "observation": {
                "seat": 0,
                "board": [{"id": 3, "grp_id": 1, "counters": {"charge": 2}}],
                "decision_objects": [{"id": 40, "grp_id": 5, "zone": "library", "owner": 0}],
            },
            "actions": [{"id": 0, "action": {"action": "pick", "card": 40}}],
        })
        self.assertEqual(decision.object(40)["grp_id"], 5, "a searched card is found like any other")
        self.assertEqual(botlib.Decision.counter(decision.object(3), "charge"), 2)
        self.assertEqual(botlib.Decision.counter(decision.object(3), "stun"), 0)
        self.assertEqual(botlib.Decision.counter({"id": 1}, "charge"), 0)

    def test_a_host_without_cards_or_limits_still_works(self):
        messages = [json.loads(line) for line in host_lines()]
        for message in messages:
            if message.get("type") == "hello":
                message.pop("cards", None)
                message.pop("limits", None)
        lines = [json.dumps(message) for message in messages]
        bot = simple_bot.SimpleBot()
        play(bot, lines)
        self.assertFalse(bot.cards)
        self.assertEqual(bot.limits.decision_ms, 5000)



class Questions(unittest.TestCase):
    SHEET = {"cards": [
        {"grp_ids": [1], "name": "Prowler", "mana_value": 4,
         "abilities": [{"ability": 0, "cost": [{"pay": "pay_life", "amount": 2}]}]},
        {"grp_ids": [2], "name": "Gollum // Meal", "mana_value": 3,
         "second_face": {"layout": "adventure", "name": "Meal", "mana_value": 1}},
    ]}

    def decide(self, question, actions, hand=(), board=()):
        bot = simple_bot.SimpleBot()
        lines = [
            json.dumps({"type": "hello", "protocol": botlib.PROTOCOL, "engine": "e", "abi": 1, "cards": self.SHEET}),
            json.dumps({"type": "game_start", "game": 0, "seat": 0, "on_play": True, "seed": 1, "deck": []}),
            json.dumps({"type": "decision", "n": 1, "question": question,
                        "observation": {"seat": 0, "hand": list(hand), "board": list(board)},
                        "actions": [{"id": i, "label": "", "action": a} for i, a in enumerate(actions)]}),
            json.dumps({"type": "bye"}),
        ]
        return bot, play(bot, lines)[1]["id"]

    def test_unknown_question_kind_and_window_are_answered(self):
        acts = [{"action": "pass"}, {"action": "play_land", "card": 5}]
        for q in ({"kind": "x_probe_future_question"}, {"kind": "priority", "window": "x_probe_future_window"}):
            _, chosen = self.decide(q, acts)
            self.assertIn(chosen, (0, 1))

    def test_no_casting_in_upkeep(self):
        acts = [{"action": "pass"}, {"action": "cast", "card": 9}]
        _, chosen = self.decide({"kind": "priority", "window": "upkeep"}, acts, hand=[{"id": 9, "grp_id": 1}])
        self.assertEqual(chosen, 0)
        _, chosen = self.decide({"kind": "priority", "window": "precombat_main"}, acts, hand=[{"id": 9, "grp_id": 1}])
        self.assertEqual(chosen, 1)

    def test_an_ability_that_costs_life_is_not_free(self):
        acts = [{"action": "pass"}, {"action": "activate", "source": 7, "ability": 0}]
        bot, chosen = self.decide({"kind": "priority", "window": "precombat_main"}, acts,
                                  board=[{"id": 7, "grp_id": 1, "controller": 0, "zone": "battlefield"}])
        self.assertEqual(chosen, 0)
        self.assertEqual(bot.cards.ability({"grp_id": 1}, 0)["cost"][0]["pay"], "pay_life")

    def test_a_second_face_has_its_own_cost(self):
        bot, _ = self.decide({"kind": "priority"}, [{"action": "pass"}])
        self.assertEqual(bot.cards.face({"grp_id": 2}, "second")["mana_value"], 1)
        self.assertEqual(bot.cards.face({"grp_id": 2})["mana_value"], 3)
        self.assertIsNone(bot.cards.face({"grp_id": 1}, "second"))


if __name__ == "__main__":
    sys.exit(unittest.main())

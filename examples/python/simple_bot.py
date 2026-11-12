"""A starter heuristic: keep, play a land, cast the biggest spell, attack, pass last.

It chooses by each action's `kind` (the stable contract), reads the question
(`decision.kind`, `decision.window`) and the card sheet (`self.cards`) to tell
cards and costs apart. It is a template for where to start, not a good
player: see bots/README.md for its scores. Replace `score` with your own idea;
`decision` has the board (`decision.mine()`, `decision.theirs()`,
`decision.you`, `decision.opponent`).
"""

import botlib

# Higher is preferred. Kinds not listed, including ones a newer engine adds,
# score DEFAULT: below anything that develops the board, above passing.
PREFERENCE = {
    "keep": 100,
    "play_land": 90,
    "cast": 80,
    "add_attacker": 70,
    "add_block": 60,
    "activate": 50,
}
DEFAULT = 10
AVOID = {"pass", "done_attacking", "done_blocking", "mulligan"}
# Cost items this bot knows how to price. Anything else (life, sacrifices,
# discards, a `pay` name from a newer engine) is a cost it will not pay.
CHEAP_COSTS = {"mana", "tap"}


class SimpleBot(botlib.Bot):
    name = "py-simple"
    version = "3"

    def score(self, action, decision):
        if action.kind in AVOID:
            return 0
        base = PREFERENCE.get(action.kind, DEFAULT)
        # Spend mana in our own main phases, not in upkeep, draw or combat.
        # An absent window (an older host) counts as a main phase.
        off_main = decision.kind == "priority" and decision.window and not decision.is_main_phase()
        if action.kind == "cast":
            if off_main:
                return -1
            # Prefer the most expensive spell we can cast, at the cost of the
            # face being cast. An unknown card still counts, with no bonus.
            face = self.cards.face(decision.object(action.get("card")), action.get("face", "own"))
            return base + (face or {}).get("mana_value", 0)
        if action.kind == "activate":
            # Never activate blind: only abilities the sheet lists, paid with
            # mana or a tap, in a main phase.
            row = self.cards.ability(decision.object(action.get("source")), action.get("ability"))
            if off_main or row is None or any(c.get("pay") not in CHEAP_COSTS for c in row.get("cost", [])):
                return -1
        return base

    def choose(self, decision):
        scores = [self.score(a, decision) for a in decision.actions]
        best = max(scores)
        return self.rng.choice([a for a, s in zip(decision.actions, scores) if s == best])


if __name__ == "__main__":
    botlib.run(SimpleBot())

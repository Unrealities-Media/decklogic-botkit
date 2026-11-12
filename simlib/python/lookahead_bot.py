"""A look-ahead bot on the simulator library, and a harness that scores it.

At each of its decisions with a real choice, the bot samples worlds its seat
cannot tell apart from the real game (`Game.sample`), tries each candidate
action in every world (`Game.clone`), plays each one out with a built-in bot at
both seats, and picks the action that won most often. Ties and decisions it
cannot look ahead on go to a built-in "prior" bot. It never reads the real
game's hidden cards: it only plays forward on samples.

    python lookahead_bot.py --lib ./libdecklogic_simlib.so --pack sim_TRK.json.gz \
        --opponent deep --pairs 20 --worlds 8

A look-ahead bot runs in-process, so `botkit match` (which hosts stdio bots)
cannot score it. `--pairs` here copies botkit's pairing: one deal played twice
with the players exchanged, scored win 1, draw 0.5, loss 0, with a standard
error over pairs. Standard library only.
"""

import argparse
import json
import math
import sys
import time

import simlib


class LookaheadBot:
    def __init__(self, game, seat, seed, worlds=8, candidates=6, rollout="quick",
                 prior="quick", budget_ms=2000, knowledge=None, pool=None):
        self.seat, self.seed = seat, seed
        self.worlds, self.candidates, self.rollout = worlds, candidates, rollout
        self.budget_ms, self.knowledge, self.pool = budget_ms, knowledge, pool
        self.prior = game.bot(prior, seat=seat, seed=seed)
        self.label = f"lookahead-w{worlds}-c{candidates}-{rollout}-over-{prior}"
        self.stats = {"decisions": 0, "searched": 0, "changed": 0, "refused": 0, "rollouts": 0}

    def _play_out(self, world, seed):
        bots = [world.bot(self.rollout, seat=s, seed=seed + s) for s in (0, 1)]
        while (s := world.seat()) is not None:
            world.apply(bots[s].choose())
        self.stats["rollouts"] += 1
        end = world.decision()
        if end["winner"] is None:
            return 0.5
        return float(end["winner"] == self.seat)

    def choose(self, game, decision):
        """An offered id for `decision`, the outstanding decision of `game`."""
        self.stats["decisions"] += 1
        prior = self.prior.choose()
        actions = decision["actions"]
        if len(actions) == 1 or self.worlds == 0:
            return prior
        started = time.perf_counter()
        ids = ([prior] + [a["id"] for a in actions if a["id"] != prior])[: self.candidates]
        score = dict.fromkeys(ids, 0.0)
        tried = 0
        for w in range(self.worlds):
            if tried and (time.perf_counter() - started) * 1000 > self.budget_ms:
                break
            try:
                world = game.sample(self.seed * 1_000_003 + decision["n"] * 101 + w,
                                    self.knowledge, self.pool)
            except simlib.SimlibError:
                # The rare decision the simulator cannot resample: no look-ahead.
                self.stats["refused"] += 1
                break
            for action_id in ids:
                branch = world.clone()
                branch.apply(action_id)
                score[action_id] += self._play_out(branch, self.seed + decision["n"] * 7 + w)
            tried += 1
        if not tried:
            return prior
        self.stats["searched"] += 1
        best = max(ids, key=lambda i: (score[i], i == prior))
        self.stats["changed"] += best != prior
        return best


def pairs(args):
    lib = simlib.Library(args.lib)
    if args.worlds and getattr(lib._dll, "dls_game_sample", None) is None:
        sys.exit(f"{args.lib} ({lib.info['engine']}) predates dls_game_sample: "
                 "use a newer release, or --worlds 0 to play the prior alone")
    engine = lib.engine(args.pack)
    decks = engine.decks()
    pool = [c for d in decks for c in d["main"]] if args.knowledge == "format-pool-v1" else None
    scores, games = [], []
    started = time.time()
    for p in range(args.pairs):
        i = p % len(decks)
        j = (i + 1 + p // len(decks)) % len(decks)
        if i == j:
            j = (j + 1) % len(decks)
        seed = args.seed * 7919 + p
        pair = 0.0
        for seat in (0, 1):
            game = engine.game([decks[i]["main"], decks[j]["main"]], seed=seed, labels=False)
            bot = LookaheadBot(game, seat, seed, args.worlds, args.candidates, args.rollout,
                               args.prior, args.budget_ms, args.knowledge, pool)
            opponent = game.bot(args.opponent, seat=1 - seat, seed=seed)
            while (s := game.seat()) is not None:
                game.apply(bot.choose(game, game.decision()) if s == seat else opponent.choose())
            end = game.decision()
            result = 0.5 if end["winner"] is None else float(end["winner"] == seat)
            pair += result / 2
            games.append({"pair": p, "decks": [decks[i]["label"], decks[j]["label"]],
                          "seat": seat, "end": end["result"], "score": result, **bot.stats})
        scores.append(pair)
        mean = sum(scores) / len(scores)
        se = (math.sqrt(sum((x - mean) ** 2 for x in scores) / (len(scores) - 1) / len(scores))
              if len(scores) > 1 else 0.0)
        print(f"pair {p + 1}/{args.pairs}: {mean:.3f} +/- {se:.3f} ({time.time() - started:.0f}s)",
              file=sys.stderr, flush=True)
    return {"engine": lib.info["engine"], "abi": lib.info["abi"], "pack": args.pack,
            "bot": bot.label, "opponent": opponent.version, "pairs": args.pairs,
            "seed": args.seed, "score": mean, "se": se,
            "seconds": round(time.time() - started), "games": games}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lib", required=True, help="the simulator library file")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--opponent", default="deep")
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--worlds", type=int, default=8, help="samples per decision; 0 plays the prior")
    ap.add_argument("--candidates", type=int, default=6, help="actions tried per decision")
    ap.add_argument("--rollout", default="quick", help="the built-in bot that plays samples out")
    ap.add_argument("--prior", default="quick", help="the built-in bot for ties and forced moves")
    ap.add_argument("--budget-ms", type=int, default=2000, help="stop adding worlds after this")
    ap.add_argument("--knowledge", choices=["blind-public-v1", "format-pool-v1"])
    ap.add_argument("--out", help="write the report with every game here")
    args = ap.parse_args()
    report = pairs(args)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "games"}))


if __name__ == "__main__":
    main()

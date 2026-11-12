"""Play traces for learners: record games between built-in bots as JSON lines.

    python simlib_traces.py --pack sim_TRK.json.gz --a deep --b deep \\
        --games 100 --seed 1 --out traces.jsonl.gz

Each game is a run of lines, versioned as ``decklogic-trace/1``:

* ``{"type": "game", "schema": "decklogic-trace/1", "engine", "abi",
  "protocol", "library", "pack", "pack_sha256", "seed", "on_play", "decks",
  "players"}``. ``players[s]`` is the bot name and its versioned label for
  seat ``s``.
* ``{"type": "step", "n", "seat", "decision", "chosen", "chosen_index"}`` for
  every decision: the protocol decision exactly as the acting seat saw it,
  the offered id the seat chose and its index in ``decision["actions"]``.
* ``{"type": "over", "result", "winner", "outcome", "steps"}``.

A reader must ignore fields it does not know, as with the protocol. The
decisions carry no labels (``labels=False``) unless ``--labels`` is passed.
Traces describe one engine and one pack: keep the ``game`` line with them.
A ``.gz`` output is gzip-compressed; a decision is about 15 KB of JSON and
compresses well.

From Python, ``record(engine, ...)`` yields the same records as dicts.
"""

import argparse
import gzip
import hashlib
import json
import random
import sys
from typing import Iterator, Optional

import simlib

SCHEMA = "decklogic-trace/1"


def record(engine: "simlib.Engine", players: tuple, seed: int, decks: Optional[tuple] = None,
           on_play: Optional[int] = None, labels: bool = False, header: Optional[dict] = None) -> Iterator[dict]:
    """One game between two built-in bots, as trace records."""
    rng = random.Random(seed)
    if decks is None:
        pool = [d["main"] for d in engine.decks()]
        decks = (rng.choice(pool), rng.choice(pool))
    on_play = rng.randrange(2) if on_play is None else on_play
    with engine.game(list(decks), seed=seed, on_play=on_play, labels=labels) as game:
        bots = [game.bot(name, seat, seed * 2 + seat) for seat, name in enumerate(players)]
        try:
            yield dict(header or {}, type="game", schema=SCHEMA, seed=seed, on_play=on_play,
                       decks=[list(d) for d in decks],
                       players=[{"bot": name, "version": bot.version} for name, bot in zip(players, bots)])
            n = 0
            while True:
                decision = game.decision()
                if decision["type"] == "over":
                    yield {"type": "over", "result": decision.get("result"), "winner": decision.get("winner"),
                           "outcome": decision.get("outcome"), "steps": n}
                    return
                chosen = bots[decision["seat"]].choose()
                index = next(i for i, a in enumerate(decision["actions"]) if a["id"] == chosen)
                yield {"type": "step", "n": n, "seat": decision["seat"], "decision": decision,
                       "chosen": chosen, "chosen_index": index}
                game.apply(chosen)
                n += 1
        finally:
            for bot in bots:
                bot.close()


def read(path: str) -> Iterator[dict]:
    """The records of a trace file, gzip or plain."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def pack_header(lib: "simlib.Library", pack: str) -> dict:
    with open(pack, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    info = lib.info
    return {"engine": info.get("engine"), "abi": info.get("abi"), "protocol": info.get("protocol"),
            "library": info.get("library"), "pack": pack.replace("\\", "/").rsplit("/", 1)[-1], "pack_sha256": digest}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Record games between built-in bots as decklogic-trace/1 lines.")
    p.add_argument("--pack", required=True)
    p.add_argument("--a", default="deep", help="seat 0's bot (random, beginner, quick, deep)")
    p.add_argument("--b", default="deep", help="seat 1's bot")
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--seed", type=int, default=1, help="first game's seed; game i uses seed + i")
    p.add_argument("--out", required=True, help="output file; .gz compresses")
    p.add_argument("--labels", action="store_true", help="keep each action's debug label")
    p.add_argument("--library", help="path to the library (default: DECKLOGIC_SIMLIB or DECKLOGIC_SIMLIB_DIR)")
    args = p.parse_args(argv)
    lib = simlib.Library(args.library) if args.library else simlib.Library.from_env()
    engine = lib.engine(args.pack)
    header = pack_header(lib, args.pack)
    opener = gzip.open if args.out.endswith(".gz") else open
    steps = wins = 0
    with opener(args.out, "wt", encoding="utf-8") as out:
        for i in range(args.games):
            for rec in record(engine, (args.a, args.b), args.seed + i, labels=args.labels, header=header):
                out.write(json.dumps(rec, separators=(",", ":")) + "\n")
                if rec["type"] == "over":
                    steps += rec["steps"]
                    wins += rec["winner"] == 0
    print(f"wrote {args.games} games, {steps} decisions, seat 0 won {wins} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

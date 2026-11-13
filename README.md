# DeckLogic bot kit

Build a Magic: The Gathering Limited bot in any language and play it against
DeckLogic's bots offline, with scores that come with error bars.

This repository holds what an outside bot builder needs and nothing else:

- **[Releases](https://github.com/Unrealities-Media/decklogic-botkit/releases/latest)**: the prebuilt `botkit` host and the simulator library for each
  platform, each with a checksum and the engine it was built from.
- **[`protocol/`](protocol/PROTOCOL.md)**: the bot protocol, `decklogic-bot/1`,
  with its JSON Schema and the recorded lists of action kinds, question kinds
  and observation fields that DeckLogic's contract tests check.
- **[`COMPATIBILITY.md`](COMPATIBILITY.md)**: what stays stable, what changes
  every week, and how to write a bot that keeps working.
- **[`examples/`](examples/)**: a Python client (`botlib.py`) and starter bots
  in Python and Rust.
- **[`registry/README.md`](registry/README.md)**: how to submit a bot.
- **[`simlib/`](simlib/README.md)**: the simulator as a shared library with a C
  header and a Rust wrapper, for training loops that need games in-process.

Start with the included [original synthetic demo](sample/demo/README.md):
it supports real games and bot validation without private data. It is not a
Magic set or a strength benchmark. For real sets, follow the
[public pack download instructions](PACKS.md). The
simulator source is not included here.

**New here? Start with [`GUIDE.md`](GUIDE.md)**: a first bot in five minutes,
then playing ours, writing one, submitting it and running a tournament.

## Two ways to play

**As a program (any language).** Your bot reads one JSON line per decision on
stdin and writes back the id of one offered action. `botkit` runs the game,
shows your bot only what its seat may see, rejects illegal answers, enforces
time limits and scores mirrored pairs:

```bash
botkit match --pack sim_TRK.json.gz --decks decks.json \
  --a "ext:python3 my_bot.py" --b deep --pairs 50 --seed 1
botkit validate --pack sim_TRK.json.gz --decks decks.json --bot "ext:python3 my_bot.py"
botkit --help
```

`botkit cards --pack sim_TRK.json.gz --out cards.json` writes the card sheet,
and `botkit decks --pack sim_TRK.json.gz --out decks.json` the decks the pack ships.

**In-process (training).** Load `decklogic_simlib` (`.dll`, `.so` or `.dylib`)
and call it from C, Rust, Python or anything with a C interface. A decision is
the same JSON the stdio protocol sends. See [`simlib/README.md`](simlib/README.md).

## Opponents

| Bot | What it is |
|---|---|
| `random-v1` | Uniformly random legal actions |
| `beginner` | A one-step heuristic with a small look-ahead over public information |
| `quick` | A stronger heuristic that also uses activated abilities well |
| `deep` | The strongest: checks for lethal and for the opponent's best replies by sampling hands the opponent could hold from the format's card pool, never its real hand |

## Versions

Each release records its engine stamp and ABI separately: published
`sim-engine-v213` has ABI `212`. The
engine changes often, about twice a day in November 2026, as cards and rules
are added. The protocol only grows within `decklogic-bot/1`: new fields and
kinds appear, and nothing is renamed or removed. Compare scores with the
same engine, pack, ordered deck cohort and evaluation settings; retain the
host/kit identity, seed schedule and faults/caps too. Read [`COMPATIBILITY.md`](COMPATIBILITY.md)
before you write much.

The staged-import and contextual-qualification changes described in
[`MAINTAINING.md`](MAINTAINING.md) are local next-kit work, not features of the
published v213 host. Use the documentation packaged with your release and
`botkit --help` to identify its supported commands.

## Licence

MIT, see [`LICENSE`](LICENSE). The prebuilt binaries are covered by the same
licence. The card data in packs is not part of this repository.

# The simulator as a library

For training loops that need many games fast, in your own process: self-play,
imitation, search over rollouts. If you only want to play your bot against
ours, the [stdio protocol](../README.md) is simpler. Use this when the pipe is
the bottleneck.

The [learned-bot handoff recipe](../LEARNED_BOTS.md) explains how to turn
training output into a self-contained stdio submission with model identity
and deployment checks.

The library is DeckLogic's Limited simulator built as a shared library
(`decklogic_simlib.dll`, `libdecklogic_simlib.so`, `libdecklogic_simlib.dylib`)
with a small C interface, [`decklogic_simlib.h`](include/decklogic_simlib.h).
It needs no simulator source. Every message is the bot protocol's JSON, so a
decision reads exactly as it does over stdio: the same `observation`,
`question` and `actions` ([`PROTOCOL.md`](../protocol/PROTOCOL.md)), checked
by the same contract tests. A bot written for one route reads the other.

## What it does

| Call | What |
|---|---|
| `dls_info()` | `{"library":"decklogic-simlib/1","protocol":"decklogic-bot/1","engine":"sim-engine-vN","abi":N}` |
| `dls_engine_open(path)` | Load a pack (`.json` or `.json.gz`) |
| `dls_engine_cards`, `dls_engine_decks` | The pack's card sheet (`decklogic-cards/1`, as `hello.cards`) and its sample decks |
| `dls_game_new(engine, spec)` | Start a game: `{"decks":[[grp ids],[grp ids]],"seed":N,"on_play":0,"labels":true}` |
| `dls_game_decision(game)` | The decision to answer, or `{"type":"over",...}` |
| `dls_game_seat(game)` | Who acts, without building the JSON |
| `dls_game_apply(game, id)` | Answer with an offered action id |
| `dls_bot_new(game, spec)` | Seat one of our bots: `{"bot":"deep","seat":1,"seed":7}` |
| `dls_bot_choose(bot, game)` | That bot's pick, **not applied**: play it, or keep it as a training label |
| `dls_game_sample(game, spec)` | One world the acting seat cannot tell apart from the game, as a new game from the same decision: `{"seed":N}`, optionally `"knowledge":"format-pool-v1"` with a `"pool"` of grp ids |
| `dls_game_clone(game)` | An independent copy in the same state |

A decision is the protocol's `decision` message plus `seat`:

```json
{"type":"decision","n":12,"seat":0,
 "observation":{...},"question":{"kind":"priority","window":"precombat_main","seat":0},
 "actions":[{"id":0,"action":{"action":"pass"},"label":"Pass"}, ...]}
```

`"labels": false` in the game spec leaves `label` out, which saves time when
you never read it (it is debug text and changes between builds anyway).

Bots: `random`, `beginner`, `quick` and `deep` are the ladder, each with its
own knowledge of the opponent. Any engine player label (`heuristic-v3`,
`search-v3:96:48`, ...) also works, with `"knowledge"` of `blind-public-v1`
(the default) or `format-pool-v1` and an optional `"pool"` of grp ids.

## Looking ahead

`dls_game_sample` and `dls_game_clone` are optional capabilities. Check the
downloaded kit's manifest and exported functions; a newer kit can retain the
same engine stamp without adding either function. The clients raise a clear
error when the loaded library lacks them. The original `sim-engine-v213`
release has neither capability.

A search bot tries actions and plays them out. Do that on a **sample**, never
on the game you are playing: a copy of the real game knows the opponent's hand
and every future draw, and so does a fresh game replayed from its seed.

`dls_game_sample` hands you one world that the seat to act cannot tell apart
from the real game. Its own view, the question and the offered actions are
identical. The opponent's hand, the order of both libraries, future shuffles
and the game seed are drawn from what that seat knows: its own decklist by
default (`blind-public-v1`), or a pool of cards the opponent's deck may hold
(`format-pool-v1`, with `pool`). Nothing hidden is read from the real game: a
sample drawn from the real game and one drawn with the same seed from another
world the seat cannot tell apart are the same game, and DeckLogic's tests check
that. Built-in bots seated in a sample assume the same knowledge.

`dls_game_clone` copies a game. Copy a sample once per action you want to
compare, so every action is judged in the same world:

```python
scores = {a["id"]: 0 for a in decision["actions"]}
for w in range(16):
    world = game.sample(seed=w)                 # one world the seat can't rule out
    for action_id in scores:
        branch = world.clone()
        branch.apply(action_id)
        bots = [branch.bot("quick", seat=s, seed=w) for s in (0, 1)]
        while (s := branch.seat()) is not None:
            branch.apply(bots[s].choose())
        scores[action_id] += branch.decision()["winner"] == decision["seat"]
best = max(scores, key=scores.get)
```

On TRK a sample costs about 80 µs and a copy about 12 µs; a play-out with
`quick` at both seats is about 20 to 40 ms from Python. A sample is refused
(`NULL`, with the reason in `dls_last_error`) once the game is over and at the
rare decision the simulator cannot resample, such as part-way through a
replacement it is replaying: answer it without looking ahead.

[`python/lookahead_bot.py`](python/lookahead_bot.py) is this bot made
whole: candidate pruning, a time budget, a built-in prior for ties and forced
moves, and a harness that scores it against a built-in bot in mirrored pairs.

The stdio protocol has no game to sample, so a bot that looks ahead runs
in-process and is scored with your own harness (mirrored pairs, as `botkit
match` does). `botkit` hosts only stdio bots.

## Rules

- **Strings belong to the library.** An engine's strings live until it is
  freed; a decision string until the next call on that game. Copy what you keep.
- **Errors** return `NULL` or `-1`; `dls_last_error()` says why, per thread.
  A refused `apply` leaves the game as it was.
- **Threads.** One game per thread at a time. Games on different threads can
  share an engine, and an engine can be freed while its games play on.
- **Determinism.** A game is a function of its decks, seed, seat on the play
  and the answers given. Same inputs, same game, on every platform.
- **Versions.** `decklogic-simlib/1` changes only if a function changes
  meaning. New functions and new message fields keep it, like the protocol.
  The engine stamp in `dls_info` changes with every engine build; compare
  results only within one stamp and pack, as with the stdio host.

## C

[`c/play.c`](c/play.c) plays one game between two built-in bots with nothing
but the header and the library, and builds warning-free with
`-std=c99 -Wall -Wextra -pedantic`:

```bash
cc -std=c99 -Iinclude c/play.c -L<lib dir> -ldecklogic_simlib -o play
LD_LIBRARY_PATH=<lib dir> ./play sim_TRK.json.gz deep quick 7
```

A bot of your own reads `dls_game_decision`'s JSON with a JSON library and
answers with `dls_game_apply`.

## Rust

[`rust/`](rust/) is a safe wrapper (`decklogic-simlib-client`) that loads the
library at run time, so your crate builds with no simulator source:

```rust
use decklogic_simlib_client::{BotSpec, Decision, GameSpec, Library};

let lib = Library::open("./libdecklogic_simlib.so")?;
let engine = lib.engine("sim_TRK.json.gz")?;
let decks = engine.decks()?;
let mut game = engine.game(&GameSpec::new([decks[0].main.clone(), decks[1].main.clone()], 7))?;
let mut deep = game.bot(&BotSpec::new("deep", 1, 7))?;
loop {
    match game.decision()? {
        Decision::Over { result, .. } => break,
        Decision::Choose { seat: 1, .. } => { let id = deep.choose(&mut game)?; game.apply(id)?; }
        Decision::Choose { actions, .. } => game.apply(actions[0].id)?,
    }
}
```

`cargo run --example play -- <library> <pack>` plays one game against Deep.

## Python

[`python/simlib.py`](python/simlib.py) is a client with no dependencies beyond
the standard library. Copy it next to your script, or `pip install` the
`python/` directory, which also installs the environments, the trace recorder
and a `simlib-traces` command.

When copying client files into your own submission, retain the accompanying
MIT `LICENSE` notice. Installable packages include that notice themselves.

For example:

```python
import simlib
lib = simlib.Library("./libdecklogic_simlib.so")      # or simlib.Library.from_env()
engine = lib.engine("sim_TRK.json.gz")
decks = engine.decks()
game = engine.game([decks[0]["main"], decks[1]["main"]], seed=7, labels=False)
deep = game.bot("deep", seat=1, seed=7)
while (d := game.decision())["type"] == "decision":
    game.apply(deep.choose() if d["seat"] == 1 else d["actions"][0]["id"])
print(d["result"], d["winner"])
```

A decision is a plain dict, so `botlib.Decision(d)` from the protocol client
reads it too.

## Reinforcement learning

[`python/simlib_env.py`](python/simlib_env.py) wraps a game as an environment,
standard library only, in the shapes Gymnasium and PettingZoo loops expect:

| Class | Shape |
|---|---|
| `SimlibEnv(engine, opponent="deep")` | One learner seat against a built-in bot: `reset(seed)` gives `(obs, info)`, `step(index)` gives `(obs, reward, terminated, truncated, info)`. Seats alternate after successful resets unless you pass `seat` |
| `SimlibAEC(engine)` | Self-play, both seats as agents `seat_0` and `seat_1`: `agent_iter()`, `last()`, `step(index)`, and a final `step(None)` per agent |

Call `reset()` successfully before reading observations or taking steps.
`close()` and a failed reset invalidate the old episode; a later successful
reset starts another. A failed reset does not consume an alternating learner
seat. Cleanup is idempotent, and inactive operations raise a reset-required
error. These lifecycle guarantees apply to the candidate client source here;
older archived clients may retain stale observations after close/reset failure.

`obs["decision"]` is the decision message above, and `obs["action_mask"]` marks
which of `max_actions` (default 128) indices are offered. You answer with an
index into `decision["actions"]`, so a fixed-size policy head works; every
offered action is legal. The reward is +1, -1 or 0 at the end of the game from
the acting seat; a game the engine stops at its turn cap is `truncated`.
`actions_cut` counts distinct observed decisions whose offer exceeded the mask,
once per decision. Repeated observation reads and reads by the inactive AEC
agent do not inflate it. It counts cut decisions, not discarded action entries.

```python
import random, simlib, simlib_env
env = simlib_env.SimlibEnv(simlib.Library.from_env().engine("sim_TRK.json.gz"), opponent="quick")
obs, info = env.reset(seed=1)
while True:
    legal = [i for i, m in enumerate(obs["action_mask"]) if m]
    obs, reward, terminated, truncated, info = env.step(random.choice(legal))
    if terminated or truncated:
        break
```

With `gymnasium` installed, `env.gymnasium_spaces()` returns
`Discrete(max_actions)` and `MultiBinary(max_actions)`, so
`action_space.sample(mask=...)` works. The decision has no fixed shape:
encode it for your network yourself. From Python on TRK, one learner step
costs about 0.5 ms against `random` and 1.7 ms against `deep`, including the
opponent's moves.

### Traces to learn from

[`python/simlib_traces.py`](python/simlib_traces.py) records games between
built-in bots as `decklogic-trace/1` JSON lines, for imitation learning or
offline analysis:

```bash
python simlib_traces.py --pack sim_TRK.json.gz --a deep --b deep --games 100 --out deep.jsonl.gz
```

A game is a `game` line (engine, ABI, pack and its SHA-256, seed, decks, each
seat's bot and versioned label), one `step` line per decision (the decision as
the acting seat saw it, the chosen id and its index) and an `over` line.
`simlib_traces.read(path)` reads them back. Five `deep` against `quick` games
on TRK are 1,305 decisions and 210 KB gzipped. Traces describe one engine and
one pack; keep the `game` line with them.

## Speed

Measured on the TRK pack, random against random, release build, one core
(DeckLogic's `throughput` example):

| | Per decision |
|---|---|
| The game alone | about 95 µs |
| The game plus writing the decision's JSON | about 155 µs |
| From Python (`simlib.py`, built-in `random` bots, `json.loads` per decision) | about 340 µs |

A decision is about 15 KB of JSON. Parsing it is on your side; a typed parser
(serde with your own structs) is faster than a generic `Value`.

## Moving from linking the simulator

A bot that used to read the simulator's Rust types directly reads the same
facts from the decision JSON here: `you`, `opponent`, `stack` and
`decision_objects` carry what the typed view carried. An encoder ported this
way was checked against the typed one on 85,848 decisions and every action
kind, with identical tensors, so a net trained on one route plays the same on
the other.

## Offline only

Like the stdio host, nothing in the DeckLogic app or a live Arena match can
reach this library.

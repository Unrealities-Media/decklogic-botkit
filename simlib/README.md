# The simulator as a library

For training loops that need many games fast, in your own process: self-play,
imitation, search over rollouts. If you only want to play your bot against
ours, the [stdio protocol](../README.md) is simpler. Use this when the pipe is
the bottleneck.

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
and a `simlib-traces` command:

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
| `SimlibEnv(engine, opponent="deep")` | One learner seat against a built-in bot: `reset(seed)` gives `(obs, info)`, `step(index)` gives `(obs, reward, terminated, truncated, info)`. Seats alternate game by game unless you pass `seat` |
| `SimlibAEC(engine)` | Self-play, both seats as agents `seat_0` and `seat_1`: `agent_iter()`, `last()`, `step(index)`, and a final `step(None)` per agent |

`obs["decision"]` is the decision message above, and `obs["action_mask"]` marks
which of `max_actions` (default 128) indices are offered. You answer with an
index into `decision["actions"]`, so a fixed-size policy head works; every
offered action is legal. The reward is +1, -1 or 0 at the end of the game from
the acting seat; a game the engine stops at its turn cap is `truncated`.

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

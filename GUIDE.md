# Build a Magic bot

Write a bot in any language, play it against ours offline, and see a score with
error bars. No Arena, no desktop app, no research tooling.

A bot is a program that reads one JSON line per decision and writes back one
action id. The host runs the game, shows your bot only what its seat may see,
rejects illegal moves, and enforces time limits. Full contract:
[`protocol/PROTOCOL.md`](protocol/PROTOCOL.md).

**Read [`COMPATIBILITY.md`](COMPATIBILITY.md) before you write much.** The
simulator gains cards, rules and action kinds every week (about two engine
releases a day in 2026-11). The protocol is held stable and only grows; your
bot has to ignore what it does not know, and the host checks that it does.

Training a learner and need millions of games in-process? The simulator also
ships as a shared library speaking the same messages: [`simlib/`](simlib/README.md).

> Start with the included [original demo pack](sample/demo/README.md). It needs
> no private assets and exercises the bot protocol with simple invented cards.
> Real-set packs are available from the [public pack feed](PACKS.md).
> The simulator source is not needed to download or use them.

## 1. Try it (5 minutes)

Download the [release for your platform](https://github.com/Unrealities-Media/decklogic-botkit/releases/latest), unpack it, and put `botkit` on your
`PATH`. From this repository's root, use the included demo pack to check an
example bot (Python 3.10+):

```bash
botkit decks --pack sample/demo/sim_DEMO.json --out decks.json
botkit validate --pack sample/demo/sim_DEMO.json --decks decks.json \
  --bot "ext:python3 random_bot.py" --cwd examples/python
```

On Windows, run these PowerShell commands from this repository's root after
unpacking the Windows archive there. Use the extracted directory name for
your release; this example uses `sim-engine-v213`.

```powershell
$botkit = '.\decklogic-botkit-sim-engine-v213-windows-x86_64\botkit.exe'
python --version
& $botkit decks --pack sample/demo/sim_DEMO.json --out decks.json
& $botkit validate --pack sample/demo/sim_DEMO.json --decks decks.json --bot "ext:python random_bot.py" --cwd examples/python
```

If your Python command is `py` or `python3`, substitute it in both commands.
PowerShell needs `& $botkit` to run the executable path stored in the variable;
the examples elsewhere in this guide use Bash line continuations (`\`).

It plays 20 games against `random-v1` and requires zero illegal actions,
timeouts or crashes, then checks latency, determinism and forward
compatibility.

**Published v213 report limitation:** validation's nested
`match_report.pack_checksum` is empty. Retain a separately exported card sheet
(`botkit cards --pack sample/demo/sim_DEMO.json --out cards.json`) and its
`pack_checksum`, or the same field in `hello.cards` from a match trace. Also
record the pack file's SHA-256 (PowerShell:
`Get-FileHash -Algorithm SHA256 sample/demo/sim_DEMO.json`). The file hash and semantic pack checksum are
different identities; keep both. The local next-kit host fixes this report
field, but that fix is not in published v213.

The runnable examples below continue with the demo. For real-set evaluation,
follow [PACKS.md](PACKS.md) and export the pack's matching decks first. Demo scores
measure protocol operation, not strength at Magic.

### Know your cards

Observations name cards by `grp_id` (Arena ids for real packs; invented local
ids for the demo). The host sends the card sheet for the
pack in play (name, cost, colours, types, power/toughness, keywords, rules
text, what each activated ability costs, and any castable second face) in `hello.cards`; `botlib.py` keeps it as `self.cards`. To browse it:

```bash
botkit cards --pack sample/demo/sim_DEMO.json --out cards.json
```

Read each offered action's structured `action` field (`action.kind` in `botlib`),
not its `label`: the field is the stable contract and `label` is debug text.
Both are described in [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md).

## 2. Play your bot against ours

```bash
botkit match \
  --pack sample/demo/sim_DEMO.json --decks decks.json \
  --a "ext:python3 simple_bot.py" --cwd examples/python \
  --b beginner --pairs 2 --seed 7 --protocol-log trace.jsonl
```

`--a` and `--b` take `random-v1`, `beginner`, `quick`, `deep`, or
`ext:<command line>`. Use the interpreter name your system has (`python3`,
`python` or `py`); a command that does not start shows up as `crash`
forfeits. `botkit --help` lists every command and flag.

A *pair* is two games with the same deal and the same deck in each table
seat, with the players exchanged, so deck and seat luck cancel. The report
gives your mean pair score (win 1, draw 0.5, loss 0) with a standard error,
forfeits by cause (`illegal`, `stale`, `timeout`, `crash`, `protocol`),
decision latency (p50, p99, max), every game (`games`: both decks, your seat,
whether you were on the play, your result) and your record by deck
(`by_deck`: when you played it, and when the opponent did).

The two-pair demo command is an execution check, not a strength comparison.
Identical scores in a few pairs can produce **zero empirical standard error**
(for example, two pair scores of 0.5 give `0.500 +/- 0.000`). That does not
establish certainty or equal playing strength. Compare real evaluations with
the same engine, pack, ordered decks and evaluation settings, and record
host/kit identity, bot versions, seeds, sample size, faults and caps.

**`--protocol-log FILE` is the best way to learn the game.** It writes every
message to and from the `--a` bot, one JSON line each way (`>` host to bot,
`<` bot to host), so you can see exactly which questions and actions arrive
and when.

**Settings go on the command line.** The host starts your bot with a cleared
environment ([`SECURITY.md`](SECURITY.md)), so an environment variable you set
is silently not there. Pass tuning parameters as arguments instead:
`--a "ext:python3 my_bot.py --aggression 2"`.

### The opponents

| Bot | What it is |
|---|---|
| `random-v1` | Uniformly random legal actions. A baseline; legal play alone does not guarantee beating it |
| `beginner` | A one-step heuristic with a small look-ahead over public information |
| `quick` | A stronger heuristic that also uses activated abilities well |
| `deep` | The strongest: a heuristic player that checks for lethal and for the opponent's best replies by sampling hands the opponent could hold, drawn from the format's card pool (never its real hand). The report names it by its player version, for example `heuristic-resolve-lethal-...-v25` |

Reference scores on the HOB sample decks (`sim-engine-v213`): the Python
example (`simple_bot.py`) scores 0.19 against `deep` and 0.88 against
`random-v1` (50 pairs, seed 1). A newcomer's one-hour heuristic reached about
0.32 against `deep`, 0.49 against `quick` and 0.66 against `beginner`.
These historical reference scores are specific to their cohorts. Compare runs
only with the same engine, pack checksum, ordered deck cohort and evaluation
settings; retain host/kit identity, bot versions, seed schedule, sample size,
faults and caps. They do not predict scores on the synthetic demo.

## 3. Write one

Start from an example:

| Example | Language | Needs |
|---|---|---|
| [`examples/python/random_bot.py`](examples/python/random_bot.py) | Python | `botlib.py` (included; `python -m unittest test_botlib` checks it) |
| [`examples/python/simple_bot.py`](examples/python/simple_bot.py) | Python | a starter heuristic using action kinds, the question and the card sheet: 0.88 vs `random-v1`, 0.19 vs `deep` (50 pairs) |
| [`examples/rust`](examples/rust/) | Rust | only `serde_json`, no simulator dependency |

In Python, [`botlib.py`](examples/python/botlib.py) is the client: copy it
next to your bot or `pip install examples/python`. Subclass `botlib.Bot`,
implement `choose(decision)`, and hand an instance to `botlib.run`. This whole
file is a working bot:

```python
import botlib

class MyBot(botlib.Bot):
    name, version = "my-bot", "1"      # shown in reports; unnamed-bot@0 otherwise

    def choose(self, decision):
        for kind in ("play_land", "cast", "add_attacker"):
            for action in decision.actions:
                if action.kind == kind:
                    return action          # an Action or its id
        return decision.actions[0]         # every decision offers at least one action

if __name__ == "__main__":
    botlib.run(MyBot())
```

Its historical TRK result was 0.075 ± 0.041 against `deep` (20 pairs, seed 1).
That reference does not predict demo performance; comparisons require the
full evaluation context listed above. What a decision gives you:

| You get | What |
|---|---|
| `decision.actions` | `Action`s with `id`, `kind` (`cast`, `play_land`, `add_attacker`, ...), `get(field)`; return one |
| `decision.kind`, `decision.window`, `decision.is_main_phase()` | What is being asked (`priority`, `declare_attackers`, `pick`, ...) and, for priority, when (`upkeep`, `precombat_main`, `stack_response`, ...). See "Questions" in `PROTOCOL.md` |
| `decision.observation`, `hand`, `mine()`, `theirs()`, `you`, `opponent`, `object(id)` | Your seat's view, never raising on a missing field |
| `self.cards.of(obj)`, `text(obj)` | The card sheet row for an observed object (`None` for a card it does not know), and its printed text (`""` when absent) |
| `self.cards.ability(obj, index)` | What an `activate` costs: `{"cost": [{"pay": "tap"}, {"pay": "pay_life", "amount": 2}], ...}`, or `None` when the sheet cannot say. Never treat an unpriced ability as free |
| `self.cards.face(obj, action.get("face"))` | The face a `cast` puts on the stack, with its own cost (an adventure's second face is not the front's) |
| `self.limits.decision_ms`, `decision.elapsed_ms()` | Your time budget per decision |
| `self.engine`, `self.abi` | The engine you are playing; log them with your results |

See the [observation-field dictionary](protocol/OBSERVATIONS.md) before using
combat values: current power/toughness already includes counters and modeled
modifiers; marked damage is separate.

In any other language, read [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md):
each decision gives you `observation` (your seat's view), `question` and
`actions`, and you answer with one action's `id`. Either way, print debugging
to **stderr**, and be deterministic given the `seed` in `game_start`:
`botkit validate` replays the first games twice and fails if the transcripts
differ.

Check a bot at any time (the same checks `register` runs, without a submission):

```bash
botkit validate --pack sample/demo/sim_DEMO.json \
  --decks decks.json --bot "ext:python3 my_bot.py" --cwd path/to/my/bot
```

## 4. Submit it

A submission is a directory with a `manifest.json` and your source (see
[`registry/README.md`](registry/README.md)). Check it exactly as we will:

```bash
botkit register --pack sample/demo/sim_DEMO.json \
  --decks decks.json --dir registry/my-bot-1
```

That runs the handshake, 20 games against `random-v1` (zero faults allowed),
the latency limit, a determinism check, and the forward-compatibility probe
(more games with fields, an action kind, a question kind and a window no engine has yet), then writes `receipt.json` binding
your source hash to the engine stamp and pack. With published v213,
`botkit verify --dir ...` checks the accepted receipt and source integrity;
it does not establish qualification for a new pack or deck cohort. Registry
entries require accepted receipts. Direct `--entrant ext:...` entries can also
play and do not carry registry qualification.

The local, unpublished next-kit host adds staged `import`, contextual
`verify --pack ... --decks ...`, and qualification settings checks. Follow
[`registry/README.md`](registry/README.md) for the version-specific intake path;
do not run next-kit commands against v213.

Default validation samples the first ten mirrored deck pairs, not every deck
or mechanic. Changing the seed changes deals, not the selected deck pairs.
Treat the result as sampled compatibility for this engine, pack and cohort.

**Until a sandbox exists we accept reviewed source only**: read
[`SECURITY.md`](SECURITY.md) for exactly what the host does and does not
isolate.

## 5. Tournament

```bash
botkit tournament --pack sample/demo/sim_DEMO.json \
  --decks decks.json --entrant random-v1 --entrant quick \
  --entrant deep --registry registry --pairs 20 --seed 1 --out out/
```

Round-robin over fixed decks with mirrored deals, standings with approximate intervals,
a cross table, and a manifest of engine stamp, pack, decks, seeds and entrant
source hashes.

Intervals use a normal approximation over pair scores, not a calibrated
small-sample guarantee. One pair or no observed variation can produce numeric
zero standard errors in raw reports; that is not certainty. The candidate next
host withholds those intervals in Markdown. Published v213 may still display
them. Keep faults/caps and full JSON, and use a declared held-out evaluation
design before treating a ranking as promotion evidence.

`--registry` adds every qualified entry in that directory. `--entrant` adds
built-in or direct `ext:` opponents; it does not select a registry entry by
name or directory. Use a dedicated registry for the admitted cohort you want
to compare, and keep retired or failed entries outside it.

## Files

| Path | What |
|---|---|
| `GUIDE.md` | This guide |
| `COMPATIBILITY.md` | What is stable, what changes every week, and how to keep a bot working |
| `SECURITY.md` | What the host isolates and what it does not |
| `protocol/` | The protocol spec, JSON Schema, and the recorded action kinds, question kinds, observation fields and wire shapes DeckLogic's contract tests check |
| `examples/` | Starter bots and `botlib.py` |
| `simlib/` | The simulator as a shared library for in-process training loops, with Rust and Python clients |
| `registry/README.md` | The submission format |

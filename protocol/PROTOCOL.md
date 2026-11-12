# Bot protocol `decklogic-bot/1`

A bot is a process. The host starts it once per game, talks to it over
stdin/stdout, one JSON object per line, and kills it when the game is over. Any
language works. The machine-readable form is [`decklogic-bot-1.schema.json`](decklogic-bot-1.schema.json);
`botkit match --protocol-log FILE` records a real exchange
(`>` host to bot, `<` bot to host).

## Messages

| Direction | `type` | Fields | Meaning |
|---|---|---|---|
| host → bot | `hello` | `protocol`, `engine`, `abi`, optional `cards`, optional `limits` | First message. Answer with `ready`. `cards` is the card sheet for the pack in play (below); `limits` is `{decision_ms, handshake_ms}`, the time limits the host enforces. |
| bot → host | `ready` | `protocol` (must be `decklogic-bot/1`), `name`, `version` | Handshake. A different `protocol` refuses the whole run. |
| host → bot | `game_start` | `game`, `seat` (0/1), `on_play`, `seed`, `deck` (your own 40 arena ids) | A new game. `seed` is yours: derive every random choice from it and the bot is reproducible. |
| host → bot | `decision` | `n`, `observation`, `question`, `actions[]` | Choose one action. |
| bot → host | `action` | `n` (echo), `id` (one of `actions[].id`) | The answer. |
| host → bot | `game_end` | `result`: `win`, `loss`, `draw`, `capped` | Final outcome from your seat. |
| host → bot | `bye` | | Exit. |

Each entry of `actions` is `{"id": 0, "label": "...", "action": {...}}`. `id`
is the index you answer with.

- **`action` is the stable contract.** It is the structured form of the
  choice: its `action` key names the kind (`cast`, `play_land`, `add_attacker`,
  `pass`, ...) and the other keys are that kind's fields (the card, targets,
  payment). Every kind and field is recorded in
  [`action-kinds.txt`](action-kinds.txt), and a test fails if the engine
  renames or removes one. Within `decklogic-bot/1` kinds and fields are only
  ever added, so treat an unknown kind as "some other choice" and an unknown
  field as absent.
- **`label` is informational.** It is the engine's Rust `Debug` text, handy
  for logs and quick experiments, and it can change with any engine build.
  Do not parse it in a bot you want to keep working.

`n` is the host's decision counter for the game. It counts both seats'
decisions, so one bot sees increasing but not consecutive values. Echo it back.

## What you are shown

`observation` is your seat's view of the game and nothing else: your hand in
full, the battlefields, graveyards, exile, the stack, both players' life and
card counts, and any card that was revealed to you. It has **no field** for the
opponent's hand or for either library; this is enforced by the type the host
serializes and is checked by a canary test on every decision of a full game.
`deck` in `game_start` is your own list, never the opponent's.

Two fields sit beside the `SeatView` fields:

- `decision_objects`: objects the current decision names that are in none of
  `hand`, `board` or `revealed`. That is the cards of a search of your own
  library once you are choosing among them, and public cards on the stack.
  Usually empty. Without it a `pick` could name a card you cannot see.
- `counters` on a `hand`, `board`, `revealed` or `decision_objects` object:
  the named counters `plus_counters` and `minus_counters` do not cover, as
  `{"charge": 2}`. Only non-zero counts appear, and the field is absent when
  there are none. The kinds so far are `charge`, `promotion`, `peace`,
  `indestructible` and `stun`; more can appear.

## Questions

`question` says what is being asked. Its `kind` names the question and its
other keys are that kind's fields; `seat` is always yours. Every kind, field
and value below is recorded in [`question-kinds.txt`](question-kinds.txt), and
a test fails if the engine renames or removes one. New kinds and fields are
added within version 1, so treat an unknown `kind` as "answer with whatever
you would play by default" and never exit on it: the `forward_compatible`
check sends one.

The answer is always one of `actions`; the question tells you how to read them.

| `kind` | Asked when | Fields | Typical actions |
|---|---|---|---|
| `mulligan` | Before the game, per hand | `taken` (mulligans so far) | `keep`, `mulligan` |
| `bottom` | After a mulligan | `count` (cards still to bottom) | `bottom` |
| `priority` | You may act | `window` (below) | `pass`, `play_land`, `cast`, `activate`, ... |
| `declare_attackers` | Your combat, one attacker at a time | | `add_attacker`, `done_attacking` |
| `attack_tax` | An attack tax applies to your attack | | a payable attack subset |
| `declare_blockers` | Their combat, one block at a time | | `add_block`, `done_blocking` |
| `assign_combat_damage` | Your attacker was blocked by several creatures | `attacker`, `blocker`, `remaining`, `lethal`, `tramples_over`, `first_strike` | how much this blocker takes |
| `pick` | An effect asks you to choose objects | `purpose` (below), `context` (the object it is about, or `null`) | the candidates |
| `trigger_targets` | Your triggered ability needs targets | `source` | one entry per legal target set |
| `trigger_order` | Several of your triggers went on the stack at once | `batch` | the orders |
| `assign_top`, `library_placement` | Scry, surveil and similar | `revealed`, `to_graveyard` / `card` | arrangements |

The remaining kinds (`untap`, `counter_replacement`, `entry_attack_defender`,
`choose_pile`, `behold_elf`, `behold_jace`, `stored_choice`,
`pick_one_per_card_type`, `cast_card_copies`, `cast_produced_within_budget`,
`remove_counters`, `choose_counter_kind`, `reveal_from_outside_the_game`,
`choose_revealed_from_outside_the_game`) belong to a few cards each. Their
fields are in `question-kinds.txt`; each appears in a
recorded transcript when one of its cards is played.

### Priority windows

`priority` carries a `window`, the point in the turn when you may act:

| `window` | When | Sorcery speed |
|---|---|---|
| `upkeep`, `draw` | Your upkeep and draw steps, stack empty | No |
| `precombat_main`, `postcombat_main` | Your main phases | Yes: lands, creatures and sorceries only here |
| `post_attack_response` | After attackers are declared | No |
| `post_block_response` | After blockers are declared | No |
| `first_strike_damage` | Between first-strike and regular combat damage | No |
| `end_step` | Each end step | No |
| `stack_response` | A spell was just cast and has not resolved | No |
| `trigger_response` | Triggered abilities were just put on the stack | No |

Most actions offered outside a main phase are instants and activated
abilities. A bot that casts whenever it can will spend its mana in upkeep;
the newcomer trial found that waiting for `precombat_main` was one of its
biggest gains. `observation.step` names the turn step itself (`untap`,
`upkeep`, `draw`, `precombat_main`, `declare_attackers`, `declare_blockers`,
`combat_damage`, `postcombat_main`, `end_step`, `cleanup`).

## Values

Field names are listed in `action-kinds.txt`, `observation-fields.txt` and
`question-kinds.txt`. Their values take these shapes:

| Value | Shape | Examples |
|---|---|---|
| A target (`targets[]` on `cast`, `activate`, ...) | `"none"` for an unused optional slot, otherwise one key naming what is targeted | `"none"`, `{"object": 23}`, `{"player": 1}`, `{"stack_item": 4}` |
| An attack defender | `kind` and `id` | `{"kind": "player", "id": 1}`, `{"kind": "permanent", "id": 31}` |
| `face` on `cast` | Which printed face is cast | `"own"`, or `"second"` for an adventure or prepare face (its cost and text are the sheet row's `second_face`) |
| `origin` on `cast` | The zone it is cast from, or an object for a granted permission | `"hand"`, `"graveyard"`, `"exile"`, `"prepared"`, `{"library_top": {"source": 12, "incarnation": 0}}` |
| `purpose` on `pick` | A name, or one key with its fields | `"discard"`, `"sacrifice"`, `{"controller_chosen_discard": {"owner": 1}}` |
| `touch` on an object in hand | What casting it does to its targets. **PascalCase**, unlike every other value | `"Neutral"`, `"Helps"`, `"Hurts"` |
| `zone` | Where an object is | `"hand"`, `"battlefield"`, `"graveyard"`, `"exile"` |
| `attack_state` | Its combat role right now | `"none"`, `"attacking"`, `"blocked"` |
| Seats | Numbers, 0 or 1 | `observation.on_play` is the seat on the play; `game_start.on_play` is `true` when that seat is yours |
| Object ids (`card`, `source`, `id`) | Numbers, stable while the object stays in one zone | `decision.object(id)` in `botlib` |
| `select_for_proliferate` | The object chosen, under `object` | `{"action": "select_for_proliferate", "object": 18}` |
| `payment` on `cast` and `activate` | Object ids spent on the cost, in cost order (lands tapped, creatures sacrificed) | `[3, 7]` |
| `mode` on `cast`, `activate` and `choose_trigger_targets` | `null` when the spell or ability is not modal, a number (the printed mode, from 0) for a choose-one, or `{"subset": mask}` for a choose-one-or-more, where bit `n` set means mode `n` is chosen | `null`, `1`, `{"subset": 5}` |

`wire-shapes.txt` lists every JSON path a decision, an action or the card
sheet has carried in sampled games, with the value types seen there (for
example `decision.actions[].action<choose_trigger_targets>.mode int|null|object`).
A path that can hold more than one type is listed with all of them, so a bot
can see where it must check the type before reading.

Every set of names above can grow. Handle an unknown one, such as a target
shape you have not seen, as something you cannot read, not as an error.

## What a card is

The observation names each card by its Arena id (`grp_id`), with its current
power, toughness, counters and a `keywords` bitmask. To know what a card *is*,
use the card sheet. The host sends it in `hello.cards` for the pack in play,
so it always matches the game. You can also write it to a file to browse:

```
botkit cards --pack sim_HOB.json.gz --out cards.json
```

The sheet (`"format": "decklogic-cards/1"`) has:

| Field | What |
|---|---|
| `pack_checksum` | The pack it was read from. Only use a sheet with games played on that pack |
| `keyword_bits` | `[{bit, name}]`: bit `n` of an observation's `keywords` mask means that keyword (`flying` is bit 0) |
| `cards` | One row per card: `grp_ids` (a basic land lists every printing), `name`, `kind` (`card` or `basic_land`), `cost` (`{2}{W}`), `mana_value`, `colors`, `types`, `subtypes`, `legendary`, `power`, `toughness`, `starting_loyalty`, `keywords`, `keyword_mask`, and `text` (printed rules text, **optional**: absent when the pack does not carry it) |
| `cards[].abilities` | The card's printed activated abilities, by the `ability` index an `activate` action names: `{"ability": 0, "cost": [{"pay": "pay_life", "amount": 2}], "sorcery_only": false, "once_each_turn": true}`. `cost` lists every item (`mana` with its `mana` text, `tap`, `pay_life`, `sacrifice`, `discard`, `loyalty`, ...); an empty list is free. An unknown `pay` name, or an `activate` whose index is not listed (an ability the object gained in play), is a cost you cannot price: treat it as expensive. Absent when the card has none |
| `cards[].second_face` | A castable second face (`layout`: `adventure` or `prepare`) with its own `name`, `cost`, `mana_value`, `types`, `subtypes`, `power`, `toughness` and optional `text`. A `cast` with `face: "second"` casts this face, at this cost |
| `tokens` | Tokens by `token_index`. **A token's `grp_id` is always 0**; look it up by the `token_index` its observed object carries |

In Python, `botlib.Cards` does the lookup (`self.cards.of(obj)`, `None` for an unknown card), or by hand: `by_id = {g: c for c in sheet["cards"] for g in c["grp_ids"]}`. Every field an observation carries is listed in [`observation-fields.txt`](observation-fields.txt).
The sheet holds printed characteristics and costs only, not how the engine
implements a card; observation fields such as `touch` and `mana_value` already
say what a spell in hand would do this turn. Like the pack, a sheet built from
Arena data is private: do not redistribute it.

## What the host enforces

| Situation | Result |
|---|---|
| `id` is not one of the offered actions (`illegal`) | You forfeit the game |
| `n` does not match the outstanding decision (`stale`) | You forfeit the game |
| No answer inside the decision limit, `hello.limits.decision_ms`, default 5 s (`timeout`) | The process is killed and you forfeit the game |
| Process exits or closes stdout (`crash`) | You forfeit the game |
| A line that is not valid protocol JSON (`protocol`) | You forfeit the game |
| A line longer than 1 MiB (`protocol`) | You forfeit the game; the host stops reading at the cap |
| `ready` names another protocol version | The run is refused (exit code 2) |

Reports show your `ready` name and version with control and
direction-override characters removed, at most 64 characters each.

A forfeit is a loss for that game only; the next game starts a fresh process.
Never fold a forfeit into your own win rate: reports count forfeits by cause.
Games are capped at the engine's turn and decision limits and counted
separately as `capped`.

## Rules for bot authors

1. Write **only** protocol lines to stdout. Debug output goes to stderr (the
   host passes it through to the terminal).
2. Flush after every line.
3. Do not read anything but stdin. The host does not give you the opponent's
   cards, and your process has no network or file access guarantee (see
   [SECURITY.md](../SECURITY.md)).
4. Be deterministic given `seed`. `botkit validate` replays the first games
   twice and fails if the transcripts differ.
5. Stay well inside the decision limit. The ladder's Deep bot answers in well
   under a second per decision on a laptop; a bot that needs seconds per
   decision makes a tournament infeasible and is refused by the latency check.

## Versioning

The string `decklogic-bot/1` changes only when a message gains a required
field or changes meaning. Within version 1, new optional fields, new action
kinds, question kinds, windows and value shapes, and new message types may appear: **ignore anything you do not know.**
`botkit validate` checks that you do (its `forward_compatible` check). The
`engine` and `abi` in `hello` name the simulator build that will run your
games; a result is only comparable to others with the same pair.

What is held stable, what changes every week, and how to write a bot that
survives it: [`COMPATIBILITY.md`](../COMPATIBILITY.md).

## The same messages in-process

For training loops, the simulator also ships as a shared library with a C
interface that returns these same messages: [`../simlib/README.md`](../simlib/README.md).

## Native Rust bots

In-tree Rust bots implement `decklogic_sim::policy::Bot` directly and are
seated by label (`random-v1`, `beginner`, `quick`, `deep`). Outside Rust
authors should prefer the protocol: see
[`examples/rust`](../examples/rust/) for a bot that depends on nothing but
`serde_json`.

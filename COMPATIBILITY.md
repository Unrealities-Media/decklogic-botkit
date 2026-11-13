# What stays stable, what changes, and how to keep your bot working

DeckLogic's simulator is not finished and won't be for a long time. We add
cards, model new rules and fix wrong ones every week. This page tells you
which parts of the kit we hold still, which parts move under you, and how to
write a bot that survives the movement.

## How fast it moves

Measured over the month to 2026-11-10:

| What | Change in a month |
|---|---|
| Engine version (`hello.engine`) | `sim-engine-v159` to `v213`: 54 releases, about two a day |
| Engine ABI (`hello.abi`), roughly one per new rules primitive | 177 to 212 |
| Action kinds the engine can offer | 37 to 49 |
| Simulator packs (`sim_*.json.gz`) | 120 updates |

Expect that rate to continue. A bot that is correct today will be offered
something new within days.

## The promise

| Part | Stability | What can change within `decklogic-bot/1` |
|---|---|---|
| Message types and their required fields (`PROTOCOL.md`, the JSON Schema) | **Stable.** Changing one needs `decklogic-bot/2`, and a host refuses a bot of the wrong version instead of misplaying it | New optional fields (for example `hello.cards`) |
| Action kinds and their fields (`protocol/action-kinds.txt`) | **Stable.** A test fails if one is renamed or removed, and that is a protocol version bump | New kinds and new fields, every week |
| Question kinds, priority windows and value shapes: targets, faces, origins, pick purposes, `touch` (`protocol/question-kinds.txt`) | **Stable**, checked the same way | New ones as rules are modeled |
| The simulator library's functions (`decklogic-simlib/1`, `simlib/README.md`) | **Stable.** A function keeps its meaning; changing one needs `decklogic-simlib/2` | New functions, and every message field the protocol adds |
| Card sheet format (`decklogic-cards/1`) | **Stable** | New optional fields (for example `abilities` and `second_face`) |
| The JSON type at every path a bot receives: number, string, object, array, bool or null (`protocol/wire-shapes.txt`) | **Stable.** A test plays seeded games and fails if a recorded path carries a new type, such as a number field that is sometimes an object | New paths, as kinds and fields are added |
| Observation (`SeatView`) field names | **Additive.** Existing fields keep their names and meaning | New fields as rules are modeled (counters, permissions, states) |
| Which cards exist, their ids and their printed text | **Changes** with every pack | Cards are added, and a pre-release card's provisional id is replaced by its real Arena id at release |
| How a card plays (rules fidelity) | **Changes.** A fix can make a card do more, less or something else | Anything. Read the release notes for your pack |
| `label` on an action | **Unstable.** Debug text | Anything, at any engine build |
| Engine strength, Deep's play, reference scores | **Changes** | Compare the same engine, pack checksum, ordered deck cohort and evaluation settings; retain host/kit identity, bot versions, seed schedule, sample size, faults and caps |

## Rules for a bot that keeps working

1. **Ignore what you do not know.** That covers unknown fields on any message
   or object, unknown message types, unknown action kinds, question kinds,
   windows and target shapes. An unknown kind
   is "some other choice": score it low, never crash on it. `botkit validate`
   enforces this (see below).
2. **Choose by structure, never by `label`.** Read `action["action"]` for the
   kind and its fields for the card and targets.
3. **Look cards up, and handle the miss.** Take the card sheet from `hello.cards`.
   The host sends the sheet for the pack in play, so it is never stale. Look
   up observed objects by `grp_id`, or by `token_index` for a token. When the
   lookup misses, fall back to what the observation itself says (`power`,
   `toughness`, `mana_value`, `keywords`, `is_creature`, `is_land`, `touch`). Don't hard-code a list of card names. If you must, key it by name,
   not id, and treat a missing entry as unknown.
4. **Don't hard-code the deck or the format.** `game_start.deck` is your deck
   for this game. Packs and sets change.
5. **Record the evaluation context.** Keep `hello.engine`, `hello.abi`,
   `hello.cards.pack_checksum`, host/kit identity, bot versions, ordered deck
   cohort/hash, evaluation settings, seed schedule, sample size, faults and
   caps. Published v213 leaves validation's nested pack checksum empty: retain
   the exported card sheet or match hello plus a pack-file SHA-256; see the
   [guide workaround](GUIDE.md). The local next-kit host fixes that field.
   A tiny sample can have zero empirical standard error without establishing
   certainty or equal strength. Demo scores are execution evidence only.
6. **Re-validate on every engine update.** Run `botkit validate` against the
   new host. The checks run in seconds.

## What the host checks for you

`botkit validate` (and `botkit register`, which runs it) fails a bot on any of:

| Check | What it catches |
|---|---|
| `handshake` | Wrong protocol string, no `ready` |
| `no_faults` | Any illegal, stale, garbage, timed-out or crashed answer in 20 games |
| `latency` | A p99 decision time above the limit |
| `determinism` | Different play from the same seeds |
| `forward_compatible` | Crashing or faulting when decisions carry fields, an action kind, a target shape, a question kind or a priority window that no engine has yet. The extra action stands for a real one, so picking it is fine. Only a fault fails |

The last check is the engine of next week, simulated today. A bot that passes
it should keep working as new cards and kinds arrive. It still only knows
what it was written to understand.

## Seeing what changed

Engine maintainers can supply comparisons from DeckLogic's `kit-notes` tool.
Those notes describe, in a bot's terms, the engine version and ABI at both
ends, every action kind, field and observation field added (or, if one was
ever removed, a **Breaking** banner), and for each pack the cards that were
added, removed or changed. Changes include printed cost, types, P/T,
keywords, text, a new Arena id, and `[rules]` when the card's modeled
behaviour changed even though its text didn't. The cards come from each
commit's pack JSON, so the notes work across any range, including packs
today's engine can no longer load. Over 2026-10-27 to 2026-11-10, for
example: 7 new action kinds, TRK gained 100 cards and moved 234
cards from provisional to real Arena ids, and five HOB and FRA cards changed
behaviour.

The local next-kit generator additionally compares recorded wire paths and
type sets. Missing historical inventories are reported as unavailable. Neither
name nor type comparisons prove unchanged field meanings or required/optional
status; those still need contract tests and maintainer review. Automated kit
release notes identify build inputs and capabilities, but do not currently run
this engine-history comparison. A kit-only update may retain the same engine.

## When we do break something

A breaking change ships as a new protocol version string. The host refuses
bots of the old version with a clear message (exit code 2) and never misplays
them. Until then, every engine update is additive at the protocol level. A
fix can still change how a card plays, and that changes how well your bot
does. That's the nature of a growing simulator, and it's why scores carry the
engine version.

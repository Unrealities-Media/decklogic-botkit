# Train a bot on Standard decks

Use the [Standard Practice catalog](https://unrealities-media.github.io/DeckLogic/standard/)
to choose fully playable 60-card main decks for offline single-game training.
The site's simulated scores describe a dated benchmark and help you choose a
varied field. Your results depend on your bot, opponent, and engine build.

## Get the deck file and matching pack

1. Download `standard-decks.json` and the matching pack from **Train a bot**.
   Save the pack as `sim_STANDARD.json.gz`. The deck file records the pack's
   corpus, minimum engine ABI, checksum and gzip SHA-256. Compare that SHA-256
   with `Get-FileHash sim_STANDARD.json.gz` in PowerShell or
   `shasum -a 256 sim_STANDARD.json.gz` in a Unix shell.
2. Obtain a [Bot Kit release](https://github.com/Unrealities-Media/decklogic-botkit/releases)
   with the required engine ABI or newer. Use a host and library from the same
   release and confirm that `botkit --help` lists `--trace` for trace collection.
3. Each deck's `main` is an array of Arena card IDs with one entry per copy.
   Keep the full pool for matchup variety. To train on a subset, write a new
   JSON file with the same `decks` array containing only the desired entries.
   A one-deck pool produces mirrors. The host checks the card IDs against the
   pack before play.

The commands below assume `botkit` is on your PATH. You can also use a path
such as `./bin/botkit` or `.\bin\botkit.exe`.

## Collect imitation data

Start with a short run, then increase the number of pairs. The trace path must
be new. Each pair uses the same deal and swaps the two bots between seats.

```sh
botkit match --pack sim_STANDARD.json.gz --decks standard-decks.json --a quick --b beginner --pairs 6 --seed 11001 --trace standard-train.jsonl > standard-train-report.json
```

Use each decision's acting-seat observation, question, and offered actions as
features. Use `chosen_action_id` as the label within that decision's action
list. If only Quick is your teacher, join the decision's `game` and `seat` to
that game's `game_end.bot_versions` to select its moves. Keep applied decisions
from complete, fault-free games with normal wins or draws. Check that the
trace ends with `match_end`, contains the expected number of games, and has the
same transcript digest as the report. Keep the pack, deck file, report, and
trace together.

## Run self-play in-process

Use the [simulator library](simlib/README.md) for repeated games without a
subprocess. Load the pack once with `dls_engine_open`. For each game, pass two
`main` arrays to `dls_game_new` in its game spec, for example
`{"decks":[main_a,main_b],"seed":11001,"on_play":0,"labels":false}` after
substituting the arrays. Read the acting seat and offer with
`dls_game_seat` and `dls_game_decision`. Pick an offered action with your
policy, or use `dls_bot_choose` for a built-in teacher, then apply the action
with `dls_game_apply`. Read the terminal result to score each seat. Free bot
and game handles after each game. Rotate deck pairings, swap policy seats for
each deal, and keep draw, cap and fault counts with the results.

## Evaluate on held-out games

Reserve distinct seeds for evaluation before you generate training games.
Keep both games of a pair in the same split, and consider holding out entire
matchups to measure transfer. Compare your baseline and trained bot on the
same deck file, seeds, opponent, engine, and pack.

```sh
botkit match --pack sim_STANDARD.json.gz --decks standard-decks.json --a "ext:python my_bot.py" --b quick --pairs 50 --seed 22001 > standard-eval.json
```

Compare mean pair score, standard error, per-deck results, and forfeits in
the two reports. Record the seed, engine stamp, opponent version, pack checksum,
and ordered deck-file identity with each evaluation. Use a fresh seed set for
the final evaluation if you used earlier evaluation results to tune the bot.

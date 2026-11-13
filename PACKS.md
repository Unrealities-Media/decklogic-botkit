# Download real-set packs

The [public sim manifest](https://unrealities-media.github.io/DeckLogic/sim/manifest.json)
lists downloadable packs. No private repository access or credentials are
needed. These are separate artifacts from the Botkit release archives; the
archives include the original synthetic DEMO pack.

Download a snapshot, retain its manifest and use the same files throughout an
evaluation. The feed can change. Its `sim_version` identifies the publishing
engine; start with that engine's Botkit release and check the host's reported
engine/ABI. An older host may not understand a newer pack. A successful load
does not establish identical behavior across engine versions.

## PowerShell

From your working directory, with `$botkit` set to the extracted executable:

```powershell
New-Item -ItemType Directory -Force packs | Out-Null
Invoke-WebRequest 'https://unrealities-media.github.io/DeckLogic/sim/manifest.json' -OutFile packs/manifest.json
$manifest = Get-Content packs/manifest.json -Raw | ConvertFrom-Json
$manifest.sim_version
$manifest.sim | Format-Table set, support_status, file
$entry = $manifest.sim | Where-Object set -eq 'HOB'
if ($null -eq $entry) { throw 'HOB is not listed in this manifest snapshot' }
$pack = Join-Path 'packs' $entry.file
Invoke-WebRequest ($manifest.base_url + $entry.file) -OutFile $pack
Get-FileHash -Algorithm SHA256 $pack
& $botkit decks --pack $pack --out packs/HOB-decks.json
& $botkit cards --pack $pack --out packs/HOB-cards.json
& $botkit validate --pack $pack --decks packs/HOB-decks.json --bot 'ext:python random_bot.py' --cwd examples/python 1> packs/HOB-validation.json 2> packs/HOB-validation.stderr.txt
if ($LASTEXITCODE -ne 0) { throw 'Validation failed; inspect retained report and stderr' }
```

For your own bot, replace the last command's entry point and `--cwd`, for
example `--bot 'ext:python -B bot.py' --cwd my-bot`. Keep the
pack/deck paths relative to the host's working directory. On other platforms,
download the same manifest and its selected `base_url` + `file` URL (for
example with `curl -fL URL -o FILE`), then use the same host commands.

## What to retain

- The downloaded manifest, pack bytes and SHA-256 of those bytes.
- Exported cards, including their semantic `pack_checksum`, and the ordered
  deck file. A gzip file hash and semantic pack checksum are different things.
- The host/release identity, bot source/version, command, settings and reports.

Published v213 validation leaves its nested `pack_checksum` empty; retain the
card export's checksum or `hello.cards.pack_checksum` from a match trace.
Do not combine decks from one pack with another. Do not silently fetch updated
packs between competitors or compare scores from different engine/pack/cohort
contexts. Default validation samples a small deck cohort, not every matchup.

The manifest's `active`, `frozen` and `preview` values describe support status,
not proof that every card is modeled. A listed real-set pack is not a claim of
complete Magic rules coverage. Keep DEMO for a small offline protocol smoke
test; use real packs to investigate strategy and report modeling limits.

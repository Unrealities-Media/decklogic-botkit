# Maintaining botkit releases

The workflow and next-kit host process described here are implemented locally
but have not been dispatched or published in this audit. Published Windows
v213 is the tested baseline; it does not provide staged `import` or contextual
qualification verification. See [intake instructions](registry/README.md) for
the two supported documentation paths.

An engine stamp identifies game semantics. It does not identify the host,
clients, documentation, or packaging. Releases therefore use
`sim-engine-vN-kit-<16 hex digits>`, with the full kit SHA256 recorded in
`release-manifest.json`. Existing engine-only tags remain historical releases;
they are never reused as proof that current SDK code has matching binaries.

## Identity and source pins

`.github/release_identity.py` hashes committed Git tree/blob identities for:

- Private `src-tauri/sim`, `src-tauri/botkit`, and `src-tauri/simlib` trees,
  including their build scripts and embedded artifacts.
- Root `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, and `.cargo`.
- `bots/protocol` and `docs/research/sim66-hob-drafted-league`, which contain
  conservative coverage of compile-time includes outside those crates.
- The complete committed public repository tree, including its SDK, demo,
  docs, manifest/export provenance, smoke test, and release workflow.

The resolved private and public commit SHAs are pinned for every build and
recorded as provenance. They are not themselves digest inputs: a private
frontend-only commit leaves the selected trees unchanged and does not force a
kit build. A host-only or public-wrapper change does. If a new local crate
dependency, build-time input, or outside `include_*` path is added, update the
private input list and its tests in the same change. Hashing whole crate trees
is deliberately conservative: test/tool changes inside them can rebuild.

Identity is based on committed content. Dirty working-tree edits are not a
release candidate. The private simulator embeds build provenance, so identical
selected source trees built from different private commits need not have
byte-identical binaries. A reused content identity retains its original build
commit in its existing manifest; the workflow does not rewrite that history.

## What gets published

Each platform archive contains the host, shared library, matching private-build
C header, licence, and the complete matching public snapshot under `sdk/`.
Only public Git-tracked files enter that snapshot; no engine source or
Arena-derived pack is copied. Keep local trials and private assets untracked.
The synthetic DEMO pack is safe to include.

Each archive's release manifest contains both source SHAs, the full kit digest,
engine/ABI/protocol/library versions, required core exports, measured optional
sample/clone capabilities, smoke outcome, and SHA256 hashes of both binaries
and the root C header. `sdk_payload.files` maps every packaged SDK file's
relative POSIX path to its exact byte SHA256, including documentation and the
demo. `sdk_payload.sha256` hashes the UTF-8 JSON map with sorted keys, compact
separators, and ASCII escapes. Symlinks and non-regular files are rejected;
SDK imports do not write bytecode into the packaged payload.
The top-level release manifest collects all three platforms and archive hashes.
`SHA256SUMS` covers the archives and top-level manifest. Release notes link to
the exact public commit's guide and explicitly report unavailable optional
capabilities. A newer kit tag with the same engine may still lack sample/clone;
consult capabilities, not the tag's apparent recency.

## Local checks and release behavior

Contributors can run these commands from the public repository root without
private source, a token, card pack or shared library:

```bash
python -B -m unittest discover -s examples/python -p test_botlib.py
python -B -m unittest discover -s .github -p 'test_release*.py'
cargo build --locked --manifest-path examples/rust/Cargo.toml
python -B .github/stdio_smoke.py -- examples/rust/target/debug/rust-random-bot
```

On Windows append `.exe` to the starter executable path. Rust uses the supported
stable 1.99.1 toolchain also selected by the release workflow.

The proposed `.github/workflows/checks.yml` runs those commands on pull requests
and pushes in exactly two hosted jobs: Ubuntu/Python 3.10 (the minimum client
version) and Windows/Python 3.13 (the supported version used by release smoke).
It uses read-only repository permissions, persists no checkout credentials,
uses no secrets or private checkout, and sets up Python and Rust. Cargo fetches
only the standalone starter dependencies pinned by its lockfile; no Python
packages are installed. Git is already supplied by the hosted runners. No API writes or
artifact publication occur. Fork contributors use the same public tests.

This lane checks Python botlib/example response contracts against the original
synthetic transcript, forward compatibility and question helpers, plus release
identity, archive/payload hashing, metadata completeness and promotion policy
with temporary local fixtures. Each job also builds the standalone Rust stdio
starter with `--locked`. `stdio_smoke.py` pipes only host messages from the
synthetic transcript, requires one valid ready and a matching decision number
with an offered action ID per decision, tolerates the fixture unknown message,
and compares action answers across two runs. It ignores recorded fixture choices
and limits each process to ten seconds. This batch-pipe smoke does not measure
per-decision timing or flushing. It does **not** load a DLL, run a real game,
qualify a bot, measure strength/latency, or establish engine integration compatibility. The release smoke/integration checks
remain separate. These proposed hosted jobs have not been dispatched in this
local audit; passing local commands do not establish hosted-runner success.

Tests use temporary Git repositories and never change real refs. To run the
smoke test locally, set `DIR` to an unpacked artifact directory, `LIB` to the
library filename, `ENGINE` and `ABI` to its expected stamp, and optionally
`SDK_ROOT` to a checkout (normally the bundled `sdk/`). It verifies every
required header export, records the two optional exports honestly, and plays
one bounded game with the required original DEMO pack. Missing optional
exports are supported; a missing core export, missing demo, or broken demo
fails the check.

Before archiving, the candidate workflow also runs packaged Python and Rust
library client tests against that platform's newly built library and packaged DEMO.
This covers single-agent and self-play environments, trace recording and core
wrapper behavior. Optional lookahead tests skip when their exports are absent;
the capability manifest still records those absences. Bytecode generation is
disabled for the test process and its children so tests do not alter the
already-hashed SDK payload. Locally, the public suite passed 11 tests with two
optional-export skips against the published Windows v213 library and DEMO;
this does not establish hosted-platform success. The Rust suite reported four
passing tests plus its compiling documentation example; one of those four
returned early because clone is absent, so this does not validate lookahead.
Rust build products go outside the package, and a local packaged rehearsal
verified that the SDK file hashes did not change. Public contributor CI compiles
the Rust library tests without requiring private engine access.

Once deployed, the workflow runs daily or on explicit dispatch. It requires a successful
paginated GitHub API release listing before deciding that a kit tag is absent;
authentication, network, and API errors fail closed. The check job requests
public-repository `contents: write` solely so drafts are visible: GitHub's
[release API](https://docs.github.com/en/rest/releases/releases#list-releases)
restricts draft listings to callers with push access. Its API calls are GETs;
the private checkout token remains read-only. `.github/release_state.py`
accepts only successful listing metadata. A matching tag skips only when it is
published, neither draft nor prerelease, and has all five expected assets:
three platform archives, `release-manifest.json`, and `SHA256SUMS`. Each must
occur once, be uploaded, and have a positive byte size. Drafts, incomplete
releases and malformed metadata fail with recovery instructions. This checks
metadata completeness, not downloaded content integrity; operators still
verify archive/manifest checksums after publication. New identities build all
platforms and publish only after smoke checks. No automatic delete/rebuild or
asset overwrite of existing releases occurs.
Public SDK edits are picked up on the next scheduled or manually requested run.

Build output from the private checkout remains in an unprinted, unuploaded
runner-local log. Failure messages identify the pinned commit, not source
lines. Identity inspection outputs only stamps, hashes and path names.

This maintenance change has been checked locally against the public Windows
v213 DLL: 16 required exports present; sample/clone absent as expected; DEMO
completed in 258 decisions. The workflow itself and Linux/macOS packaging
have not been dispatched as part of this local audit.

## Ownership and handoffs

Assign these roles when integrating a change. This public repository owns
handwritten clients, starters, optional C API declarations, documentation and
release workflows. DeckLogic owns the engine contracts, core C API, original
DEMO and synthetic transcript; its exporter updates only those inputs.

The public main C header includes the exported core header and declares optional
extensions separately. Declarations never imply that a library implements an
optional function: use capability checks and retain absence guards. Private
client copies are regression fixtures, not inputs to public releases. Make
client changes here and run public CI plus packaged-client checks. If private
tests need a newer client, adopt a reviewed public revision explicitly rather
than synchronizing both directories in both directions.

From a private DeckLogic checkout, inspect the export before updating it:

```powershell
node bots/export-kit.mjs --dest ../decklogic-botkit --check
node bots/export-kit.mjs --dest ../decklogic-botkit --write
node bots/export-kit.mjs --dest ../decklogic-botkit --check
```

These commands are local only. The generated-payload manifest hashes
exported files; the release manifest additionally hashes the complete packaged
SDK. Exporter success does not replace public documentation or client review.

| Trigger / owner | Checklist | Recovery |
|---|---|---|
| New bot / author and source reviewer | Start with DEMO; review source, dependencies and model provenance; keep logs outside the entry; install dependencies deliberately | Correct the submission before intake; neither author receipts nor `network:false` establish isolation |
| Reviewed entry / intake maintainer | Follow the version-specific staging path; validate the exact copy; with next-kit, verify current pack/decks/settings before registry play | Keep failed `.botkit-pending-*` copies outside active registry; inspect receipt/errors; existing entries are not replaced |
| Engine, pack, cohort or evaluation settings change / intake maintainer | Retain old artifacts/receipt; requalify unchanged source in a new workspace; use the intended decision timeout | Preserve old qualified environment; keep failures out of new registry; change bot version only when code/weights change |
| Rules or contract change / engine and SDK owners | Run relevant owner/contract checks; decide compatibility explicitly; update inventories and author notes | Do not bless removed fields or changed meanings as additive updates |
| Core contract/header/demo change / engine owner | Check allow-listed export, inspect exact payload hashes and relevant contract/demo checks | Refuse removed core functions until engine revisions or an explicit ABI migration agree; regenerate DEMO without private card data |
| Client/starter/optional declaration change / public SDK owner | Edit this repository; run client CI and packaged-client checks against supported libraries | Preserve absence guards and document the first supporting kit; never infer binary capability from declarations |
| Host behavior or public prose change / public docs owner | Update affected guides together; name the first supporting kit and optional capabilities; retain old-release instructions where needed | Correct contradictions before release; HEAD documentation must not imply old binaries gained new features |
| Release candidate / release maintainer | Review and commit both snapshots; inspect all public tracked files for private data; update identity inputs for new build dependencies/includes; pin both SHAs | Dirty work is not a release candidate; stop before packaging unexpected private files |
| Authorized release / operator | Check identity, all platform builds, required exports, header/SDK hashes, DEMO smoke and version-pinned links; report optional absence honestly | API/auth errors stop; reproduce private build failures locally at pinned SHA without public source logs |
| Published artifact / operator | Verify three archives, aggregate manifest, checksums and intended latest target | Follow explicit incomplete-release recovery below; do not silently replace releases |

The local next-kit receipt now records evaluation settings and admission
compares them: handshake/decision durations, all game configuration fields,
card-sheet hash and probe mode. `register`, `import` and contextual `verify`
accept `--decision-timeout-ms`. Keep these budgets consistent with the intended
tournament. Default ten-pair validation remains a sample of the fixed deck
schedule, not universal qualification or evidence of strength. Record actual
sample size, caps and faults alongside comparisons.

## Failure recovery and promotion

- Authentication/network/API lookup errors are failures, not evidence that a
  release is absent. Renew the scoped private read token privately when needed.
- An existing draft, prerelease or incomplete exact kit release stops the run.
  Inspect its pinned identity, publication state and assets first. An authorized
  operator must choose whether to recover assets from the same verified build
  or replace that incomplete release under the project's release process and
  any repository immutability restrictions. Do not mix artifacts from different
  builds. The workflow performs no automatic deletion, repair or overwrite.
  Rerunning only skips once metadata is complete; verify actual checksums too.
- Manual dispatch accepts a private ref and an explicit `promote_latest`
  boolean, default **false**, even for `main`. Historical builds therefore pass
  `--latest=false`; select promotion only after reviewing the intended latest
  target. Scheduled current-`main` builds pass `--latest=true`. Omitting the
  flag would allow GitHub's automatic latest selection, per the
  [CLI documentation](https://cli.github.com/manual/gh_release_create).
  A skipped complete release is not promoted by this workflow; changing its
  latest status requires a separately authorized operator action.
- Keep prior artifacts and receipts for rollback/replay. Requalification of
  unchanged source does not require a bot-version bump; changed decisions or
  model weights do. Never auto-update entrants during an evaluation.

Unsupported: unreviewed binary or desktop one-click intake, automatic dependency
installation, runtime attestation, process-tree/resource/network/filesystem
confinement, equal built-in/external search access, draft/build tournaments,
and automatic pack updates during evaluation. Real-set packs have a separate
[public feed](PACKS.md); SDK archives include only DEMO. DEMO establishes execution, not Magic-set
fidelity or playing strength. None of this documentation authorizes a release,
workflow dispatch, external message or remote mutation.

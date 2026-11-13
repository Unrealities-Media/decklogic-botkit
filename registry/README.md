# Submitting a bot

Each accepted entry is a directory: your source, a `manifest.json`, and the
`receipt.json` that `botkit register` wrote. A tournament loads the entries here
(`--registry registry`), re-checks every receipt, and refuses an entry
whose source no longer hashes to what was validated.

The commands below distinguish published v213 from local next-kit changes.
No next-kit release has been published as part of this audit.

## manifest.json

```json
{
  "schema": "decklogic-bot-manifest/1",
  "name": "my-bot",
  "version": "1",
  "author": "Your name or team",
  "contact": "how to reach you",
  "protocol": "decklogic-bot/1",
  "entry": "python bot.py",
  "runtime": "python>=3.10, numpy",
  "license": "your license",
  "resources": { "p99_ms": 50, "memory_mb": 500, "network": false }
}
```

| Field | Rule |
|---|---|
| `name`, `version` | Letters, digits, `-`, `_`, `.`. The entry's id is `name@version`; a changed bot gets a new version and a new directory (`name-version`) |
| `entry` | Command line run with the submission directory as its working directory. No shell: whitespace-separated, quote with `"` |
| `runtime` | The language and packages your entry needs, so a reviewer can reproduce the environment |
| `resources` | What you expect to need. Declared, not enforced yet (see `../SECURITY.md`). `network: true` is refused |

## Accepting an entry

For compiled bots, the [Rust starter packaging recipe](../examples/rust/README.md)
shows how to retain source/lockfile and place the executable outside excluded
build caches. Its Windows relative-executable recipe requires next-kit.

1. Read the source (`../SECURITY.md`: reviewed source only).
2. With **published v213**, copy reviewed source into a staging directory
   outside the active registry, then run
   `botkit register --pack ... --decks ... --dir staging/<name>-<version>`.
   Move only a passing entry into the active registry. Bare `verify --dir ...`
   checks source integrity/acceptance; manually revalidate when the engine,
   pack, decks or evaluation context changes.
3. Retain the directory and receipt under the maintainer's review process.
   Changed code or model weights need a new bot version. Requalification of
   unchanged source does not; archive its prior receipt outside the entry.

Retain evaluated bytes, not just a source Git commit. Checkout filters and
line-ending conversion can change files and invalidate a receipt. Keep a
byte-preserving archive with its SHA-256 beside the retained host, pack, decks,
settings and reports; restore it separately and verify before reproduction.
Unix executables also need permissions preserved by the archive/extraction
tool: the source hash covers paths and bytes, not permission bits. If using Git
to store evaluated snapshots, deliberately disable text conversion for that
snapshot directory outside the payload and verify an actual restored checkout.

**Local next-kit host (unpublished):**

```bash
botkit import --source incoming/my-bot --registry registry --pack pack.json.gz --decks decks.json
botkit verify --dir registry/my-bot-1 --pack pack.json.gz --decks decks.json
```

Import discards submitted receipts, stages a copy outside tournament discovery,
and validates before admitting it. Existing entries are not replaced. Failed
copies remain in the reported `.botkit-pending-*` directory for diagnosis.
Links/non-regular files are refused. Dependencies must already be deliberately
installed; import runs no installers, build scripts or model downloads.

Next-kit contextual verification and registry admission check engine/ABI,
pack, ordered decks, qualification policy and evaluation settings, including
handshake/decision limits, game configuration, card-sheet hash and probe mode.
`register`, `import` and contextual `verify` accept `--decision-timeout-ms`;
use the same intended budget for qualification and tournament play. Bare
`verify --dir ...` remains source verification only. Legacy receipts require
requalification before next-kit registry play.
The local candidate now uses `decklogic-botkit-qualification/3`: UTF-8 path
components are hashed without treating a literal Unix backslash as a directory
separator. Earlier candidate receipts require requalification, even where their
ordinary source hash remains unchanged. This policy is not part of published v213.

Keep logs and reports outside the entry. Package required distributable assets
alongside source, outside excluded cache directories (`.venv`, `node_modules`,
`target`, bytecode and `.git`). Installed runtimes/dependencies are reviewed
separately and are not attested by the source receipt.
This applies to every bot-owned script, executable, model, weight and required
data file, not only a compiled binary. `__pycache__`, `*.pyc` and every nested
file named `receipt.json` are excluded too. Reserve those locations for caches
and host evidence. In-place registration is not a workaround for import's
payload exclusions; review all required runtime inputs explicitly. The local
next-kit candidate rejects whole command-line arguments naming existing files
in excluded paths, or relative files outside the submission, during register,
import and verify. It does not parse inline code, module names, option values
or dynamically loaded assets. Separately installed runtimes remain allowed.
Existing files inside the submission must use relative paths, so imports run
the copied payload instead of an absolute path back to its original directory.
Published v213 does not include this guard.
Empty directories are not copied by next-kit import. Create required empty
working directories at runtime and keep writable logs/reports outside the entry.
Import and archival change the entry's parent and absolute path. Resolve
bot-owned scripts/models from inside the submission, not an adjacent
`../shared` directory or a cached staging path. Verification checks integrity
and qualification context without launching the bot; inspect comparison fault
counts after moving it. A tournament can exit successfully while reporting
bot crash forfeits.

An interrupted import may leave a partial `.botkit-pending-*` copy without a
receipt. Confirm its owning process has stopped, retain available evidence,
and retry from the original reviewed source. Do not manually move that pending
copy into the active registry. Archive or remove only the exact abandoned
directory after confirming ownership; import does no automatic cleanup.

`receipt.json` records the manifest, the SHA-256 of every source file (sorted
paths and bytes, excluding the receipt, build output and bytecode), the engine
stamp, the pack checksum, the deck hash, the seed and the validation result.

# Submitting a bot

Each accepted entry is a directory: your source, a `manifest.json`, and the
`receipt.json` that `botkit register` wrote. A tournament loads the entries here
(`--registry registry`), re-checks every receipt, and refuses an entry
whose source no longer hashes to what was validated.

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

1. Read the source (`../SECURITY.md`: reviewed source only).
2. `botkit register --pack ... --decks ... --dir registry/<name>-<version>`.
3. Commit the directory including `receipt.json`. Any later edit to a source
   file invalidates the receipt; register again under a new version.

`receipt.json` records the manifest, the SHA-256 of every source file (sorted
paths and bytes, excluding the receipt, build output and bytecode), the engine
stamp, the pack checksum, the deck hash, the seed and the validation result.

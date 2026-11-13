# Rust starter and a portable submission

This crate reads `decklogic-bot/1` JSON lines and selects a seeded random legal
action. It has no simulator dependency. Replace the policy, keep protocol
handling and fallback behavior, and update both the handshake identity and
submission manifest when releasing your own bot.

Build from this repository's root with a Rust toolchain:

```powershell
cargo build --release --locked --manifest-path examples/rust/Cargo.toml
```

## Package for the local next-kit importer on Windows

The next-kit host is not published yet. Published v213 does not provide the
staged `import` command or the Windows relative-executable fix used below.
See [the version-specific registry guide](../../registry/README.md).

Build products under `target` are excluded from imported payloads. Copy the
distributable executable into `bin` alongside reviewed source and the lockfile.
Use a fresh submission directory; do not copy the whole build cache:

```powershell
if (Test-Path -LiteralPath incoming/rust-random) { throw 'Choose a fresh submission directory' }
New-Item -ItemType Directory -Path incoming/rust-random/src,incoming/rust-random/bin -Force
Copy-Item -LiteralPath examples/rust/Cargo.toml,examples/rust/Cargo.lock -Destination incoming/rust-random
Copy-Item -LiteralPath examples/rust/src/main.rs -Destination incoming/rust-random/src
Copy-Item -LiteralPath examples/rust/target/release/rust-random-bot.exe -Destination incoming/rust-random/bin
Copy-Item -LiteralPath examples/rust/manifest.windows.json -Destination incoming/rust-random/manifest.json
Copy-Item -LiteralPath LICENSE -Destination incoming/rust-random
```

Review and edit the manifest's author/contact, bot identity, runtime target and
resource declarations. Record the actual compiler version and build command
with your submission. A reviewer builds deliberately before import; the host
does not run Cargo, install dependencies or download models. A recipient needs
the executable's target platform and system libraries, not a Rust installation.

With the next-kit host available as `./botkit.exe`:

```powershell
./botkit.exe decks --pack sample/demo/sim_DEMO.json --out demo-decks.json
./botkit.exe import --source incoming/rust-random --registry registry --pack sample/demo/sim_DEMO.json --decks demo-decks.json
./botkit.exe verify --dir registry/rust-random-1 --pack sample/demo/sim_DEMO.json --decks demo-decks.json
./botkit.exe tournament --registry registry --entrant random-v1 --pack sample/demo/sim_DEMO.json --decks demo-decks.json --pairs 2 --out reports/rust-demo
```

`--registry` includes every qualified entry in that directory. Do not repeat
its name or directory as `--entrant`; that option adds built-in or direct `ext:`
opponents. Use a dedicated registry for a selected cohort. Two pairs here are a
process check, not a strength estimate; import uses default qualification.

For another platform, build a matching executable, retain its execute permission,
and change `entry` and `runtime` accordingly. The concrete packaging/import
recipe above was checked locally on Windows; it is not a Linux/macOS runtime claim.

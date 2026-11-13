# What the bot host isolates, and what it does not

A protocol bot is a process the host starts on your machine. Treat third-party
bots as untrusted code. **Until a real sandbox exists, run only source you have
read, or run it inside a throwaway VM or container.**

## Enforced by the host

| Control | How |
|---|---|
| One process per game | Each game starts fresh process memory. Files and other external state can persist between games |
| Handshake limit (20 s) and decision limit (5 s, `--decision-timeout-ms`) | A reply timeout forfeits the game. Published v213 can still block while writing to a bot that stops reading; see next-kit changes below |
| Hidden observation fields | The bot receives its seat's `SeatView` and own deck, without the opposing hand or library contents. This alone does not prevent reconstruction from disclosed seeds; see below |
| Legality | The answer is an index into the offered set; anything else forfeits. A bot cannot construct an illegal move |
| Scrubbed environment | The child inherits only `PATH`, `SystemRoot`, `TEMP`, `TMP`, `HOME`, `USERPROFILE`, `PYTHONUTF8`. Other environment variables are removed; accessible files and services may still contain credentials |
| Working directory | Set to the submission directory |
| No network bots accepted | A manifest with `resources.network = true` is refused |
| Source integrity | `receipt.json` binds the validated source hash; `botkit verify` and the tournament refuse an entry whose files changed since validation |

## Published v213 and local next-kit changes

The **local, unpublished next-kit host** includes pipe writes in handshake and
decision deadlines, bounds reply lines to 64 KiB (including newline), and
bounds queued replies. This does not cap the bot's own memory, kill descendant
processes, or make logging/filesystem operations interruptible. These changes
are not present in the downloaded v213 binary.

Published v213 derives the wire bot seed reversibly from the deal seed. With
known deck arrays, that can reveal hidden opening hands through replay. The
local next-kit `independent-public-policy-v1` scheme makes policy randomness
independent of deal seeds. Public/default deal seeds still permit replay.
Confidential evaluation therefore also requires a held-out high-entropy deal
seed, frozen submissions and reports/secrets unavailable to running bots.
Source review and seat-only JSON do not provide that isolation.

Next-kit registry admission also checks the receipt's qualification policy,
engine/ABI, pack, ordered decks and evaluation settings. Bare `verify --dir`
is an integrity check; add `--pack` and `--decks` for contextual qualification
on a supporting host. See [version-specific intake](registry/README.md).

## Not enforced

| Gap | Consequence | Mitigation until fixed |
|---|---|---|
| No memory or CPU cap | A bot can exhaust RAM | Run on a machine you can restart; planned: Windows Job Objects, Linux cgroups/rlimit |
| No network denial | A bot can open sockets | Run offline; planned: namespace/firewall rule per child |
| No filesystem confinement | A bot can read or write any file the host's user can | Run as a restricted user or in a VM; the working directory is a default, not a jail |
| Children of the bot | A bot can spawn processes that outlive the kill | Planned: kill by Job Object/process group |
| No CPU-fairness | Slow bots slow the tournament | The latency check at registration; the decision limit at play |

## Acceptance policy

Accept **reviewed source** only, with a named author and contact. Do not run
binaries submitted without source. A registry entry is the review record: the
manifest, the exact source hash, and the validation receipt.

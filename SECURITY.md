# What the bot host isolates, and what it does not

A protocol bot is a process the host starts on your machine. Treat third-party
bots as untrusted code. **Until a real sandbox exists, run only source you have
read, or run it inside a throwaway VM or container.**

## Enforced by the host

| Control | How |
|---|---|
| One process per game | A crash, hang or garbage costs that bot that game and nothing else; no state carries over |
| Handshake limit (20 s) and decision limit (5 s, `--decision-timeout-ms`) | The process is killed on expiry and forfeits the game |
| Hidden information | The bot receives only its seat's `SeatView` and its own deck; the type has no field for the opponent's hand or a library. A canary test checks every decision of a full game |
| Legality | The answer is an index into the offered set; anything else forfeits. A bot cannot construct an illegal move |
| Scrubbed environment | The child starts with an empty environment plus `PATH`, `SystemRoot`, `TEMP`, `TMP`, `HOME`, `USERPROFILE`, `PYTHONUTF8`; no tokens or credentials are inherited |
| Working directory | Set to the submission directory |
| No network bots accepted | A manifest with `resources.network = true` is refused |
| Source integrity | `receipt.json` binds the validated source hash; `botkit verify` and the tournament refuse an entry whose files changed since validation |

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

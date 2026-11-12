"""Release smoke test: the packaged library loads and states the engine the
release is named after. Run by .github/workflows/release.yml."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simlib", "python"))
import simlib  # noqa: E402

info = simlib.Library(os.path.join(os.environ["DIR"], os.environ["LIB"])).info
print(info)
assert info["engine"] == os.environ["ENGINE"], info
assert info["abi"] == int(os.environ["ABI"]), info
assert info["protocol"] == "decklogic-bot/1", info

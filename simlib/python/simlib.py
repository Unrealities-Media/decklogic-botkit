"""Python client for the DeckLogic simulator library, `decklogic-simlib/1`.

Standard library only (ctypes and json). Load the prebuilt library, start
games, read each decision as the bot protocol's JSON (`decklogic-bot/1`) and
answer it, with DeckLogic's own bots available as opponents or teachers:

    import simlib
    lib = simlib.Library("./libdecklogic_simlib.so")      # or Library.from_env()
    engine = lib.engine("sim_TRK.json.gz")
    decks = engine.decks()
    game = engine.game([decks[0]["main"], decks[1]["main"]], seed=7, labels=False)
    deep = game.bot("deep", seat=1, seed=7)
    while (d := game.decision())["type"] == "decision":
        game.apply(deep.choose() if d["seat"] == 1 else d["actions"][0]["id"])
    print(d["result"], d["winner"])

A decision dict has `n`, `seat`, `observation`, `question` and `actions`
exactly as PROTOCOL.md describes, so `botlib.Decision(d)` reads it too.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from typing import Any, Optional

LIBRARY = "decklogic-simlib/1"

if sys.platform == "win32":
    FILE_NAME = "decklogic_simlib.dll"
elif sys.platform == "darwin":
    FILE_NAME = "libdecklogic_simlib.dylib"
else:
    FILE_NAME = "libdecklogic_simlib.so"


class SimlibError(RuntimeError):
    """The library refused a call; the message is its `dls_last_error`."""


_P = ctypes.c_void_p
_S = ctypes.c_char_p


class Library:
    """The loaded library. Engines, games and bots keep a reference to it."""

    def __init__(self, path: str):
        self._dll = ctypes.CDLL(path)
        sig = {
            "dls_info": ([], _S),
            "dls_last_error": ([], _S),
            "dls_engine_open": ([_S], _P),
            "dls_engine_cards": ([_P], _S),
            "dls_engine_decks": ([_P], _S),
            "dls_engine_free": ([_P], None),
            "dls_game_new": ([_P, _S], _P),
            "dls_game_decision": ([_P], _S),
            "dls_game_seat": ([_P], ctypes.c_int32),
            "dls_game_apply": ([_P, ctypes.c_uint32], ctypes.c_int32),
            "dls_game_free": ([_P], None),
            "dls_bot_new": ([_P, _S], _P),
            "dls_bot_choose": ([_P, _P], ctypes.c_int64),
            "dls_bot_version": ([_P], _S),
            "dls_bot_free": ([_P], None),
        }
        for name, (args, res) in sig.items():
            fn = getattr(self._dll, name)
            fn.argtypes = args
            fn.restype = res
        self.info: dict = json.loads(self._dll.dls_info())
        if self.info.get("library") != LIBRARY:
            raise SimlibError(f"the library speaks {self.info.get('library')}, this client {LIBRARY}")

    @classmethod
    def from_env(cls) -> "Library":
        """`DECKLOGIC_SIMLIB` (the file) or `DECKLOGIC_SIMLIB_DIR` (its directory)."""
        if os.environ.get("DECKLOGIC_SIMLIB"):
            return cls(os.environ["DECKLOGIC_SIMLIB"])
        return cls(os.path.join(os.environ.get("DECKLOGIC_SIMLIB_DIR", "."), FILE_NAME))

    def _error(self) -> SimlibError:
        message = self._dll.dls_last_error()
        return SimlibError(message.decode("utf-8", "replace") if message else "unknown error")

    def _text(self, raw: Optional[bytes]) -> str:
        if raw is None:
            raise self._error()
        return raw.decode("utf-8")

    def engine(self, pack: str) -> "Engine":
        """Load a pack (`.json` or `.json.gz`)."""
        raw = self._dll.dls_engine_open(os.fsencode(pack))
        if not raw:
            raise self._error()
        return Engine(self, raw)


class _Handle:
    _free = ""

    def __init__(self, lib: Library, raw: int):
        self._lib = lib
        self._raw = raw

    def close(self) -> None:
        if self._raw:
            getattr(self._lib._dll, self._free)(self._raw)
            self._raw = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Engine(_Handle):
    """A loaded pack. Games may outlive it."""

    _free = "dls_engine_free"

    def cards(self) -> dict:
        """The card sheet (`decklogic-cards/1`), as `hello.cards` carries it."""
        return json.loads(self._lib._text(self._lib._dll.dls_engine_cards(self._raw)))

    def decks(self) -> list:
        """The decks the pack ships: `[{"label": ..., "main": [grp ids]}]`."""
        return json.loads(self._lib._text(self._lib._dll.dls_engine_decks(self._raw)))

    def game(self, decks, seed: int, on_play: int = 0, labels: bool = True,
             deal_model: Optional[str] = None) -> "Game":
        spec: dict[str, Any] = {"decks": [list(decks[0]), list(decks[1])], "seed": seed,
                                "on_play": on_play, "labels": labels}
        if deal_model:
            spec["deal_model"] = deal_model
        raw = self._lib._dll.dls_game_new(self._raw, json.dumps(spec).encode())
        if not raw:
            raise self._lib._error()
        return Game(self._lib, raw)


class Game(_Handle):
    """One game. Use it from one thread at a time."""

    _free = "dls_game_free"

    def decision_text(self) -> str:
        return self._lib._text(self._lib._dll.dls_game_decision(self._raw))

    def decision(self) -> dict:
        """`{"type": "decision", ...}`, or `{"type": "over", "result", "winner"}`."""
        return json.loads(self.decision_text())

    def seat(self) -> Optional[int]:
        """The seat to act, or `None` once the game is over."""
        seat = self._lib._dll.dls_game_seat(self._raw)
        return None if seat < 0 else seat

    def apply(self, action_id: int) -> None:
        if self._lib._dll.dls_game_apply(self._raw, action_id) != 0:
            raise self._lib._error()

    def bot(self, name: str, seat: int, seed: int, knowledge: Optional[str] = None,
            pool: Optional[list] = None) -> "Bot":
        """Seat one of DeckLogic's bots: `random`, `beginner`, `quick`, `deep`,
        or an engine player label (with optional `knowledge` and `pool`)."""
        spec: dict[str, Any] = {"bot": name, "seat": seat, "seed": seed}
        if knowledge:
            spec["knowledge"] = knowledge
        if pool is not None:
            spec["pool"] = list(pool)
        raw = self._lib._dll.dls_bot_new(self._raw, json.dumps(spec).encode())
        if not raw:
            raise self._lib._error()
        return Bot(self._lib, raw, self)


class Bot(_Handle):
    """A built-in bot seated in one game."""

    _free = "dls_bot_free"

    def __init__(self, lib: Library, raw: int, game: Game):
        super().__init__(lib, raw)
        self._game = game

    def choose(self) -> int:
        """Its pick for the game's outstanding decision, as an offered id. Not applied."""
        action_id = self._lib._dll.dls_bot_choose(self._raw, self._game._raw)
        if action_id < 0:
            raise self._lib._error()
        return action_id

    @property
    def version(self) -> str:
        return self._lib._text(self._lib._dll.dls_bot_version(self._raw))

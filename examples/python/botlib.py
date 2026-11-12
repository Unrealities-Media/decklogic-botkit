"""The Python client for `decklogic-bot/1` bots.

Copy this file next to your bot, or install it (`pip install bots/examples/python`)
and `import botlib`. Standard library only.

    import botlib

    class MyBot(botlib.Bot):
        name, version = "my-bot", "1"

        def choose(self, decision):
            for action in decision.actions:
                if action.kind == "play_land":
                    return action
            return decision.actions[0]

    botlib.run(MyBot())

`choose` may return an `Action` or its integer `id`. Everything the host sends
is also there raw (`decision.raw`, `action.raw`), and the older signature
`choose(self, observation, question, actions)` still works for bots written
before the client.

**The engine grows every week** (`bots/COMPATIBILITY.md`). New action kinds,
new fields and new cards will appear. This client never raises on an unknown
one: an unknown kind is just a `kind` string you have no rule for, an unknown
card is `None` from `cards.of`, an unknown question is just a
`decision.kind` you have no rule for, and an unknown message is ignored. Keep your
bot the same way. `botkit validate` checks it with its `forward_compatible`
probe.

Rules the host enforces: answer every decision with the `id` of one offered
action within `self.limits.decision_ms`; anything else forfeits the game.
Write only protocol lines to stdout; use `botlib.log` (stderr) for debugging.
"""

from __future__ import annotations

import json
import random
import sys
import time
from typing import Any, Iterable, Optional

PROTOCOL = "decklogic-bot/1"
__version__ = "1.3.0"


def log(*parts: Any) -> None:
    """Print to stderr, which the host passes through. Never print to stdout."""
    print(*parts, file=sys.stderr, flush=True)


class Cards:
    """The card sheet the host sends in `hello` (`decklogic-cards/1`).

    `cards.of(obj)` looks up any observed object (a card in hand, on the
    battlefield, on the stack...) and returns its sheet row as a dict, or
    `None` for a card the sheet does not know. Always handle `None`: the
    engine adds cards every week. The host sends a fresh sheet for every game,
    so a miss means an older host or a hand-built game, never a stale file of
    yours.
    """

    def __init__(self, sheet: Optional[dict] = None):
        sheet = sheet or {}
        self.sheet = sheet
        self.by_id = {g: c for c in sheet.get("cards", []) for g in c.get("grp_ids", [])}
        self.tokens = {t["token_index"]: t for t in sheet.get("tokens", []) if "token_index" in t}
        self.keyword_bits = {b["name"]: b["bit"] for b in sheet.get("keyword_bits", [])}

    def __bool__(self) -> bool:
        return bool(self.by_id)

    def of(self, obj: Optional[dict]) -> Optional[dict]:
        if not obj:
            return None
        token = obj.get("token_index")
        if token is not None:
            return self.tokens.get(token)
        return self.by_id.get(obj.get("grp_id"))

    def name(self, obj: Optional[dict], default: str = "?") -> str:
        row = self.of(obj)
        return row["name"] if row else default

    def text(self, obj: Optional[dict]) -> str:
        """Printed rules text, or `""` when the card is unknown or the pack carries none."""
        row = self.of(obj)
        return (row or {}).get("text") or ""

    def ability(self, obj: Optional[dict], index: Any) -> Optional[dict]:
        """The printed activated ability `index` of an observed object, or `None`.

        `None` also means an ability the object gained in play, whose cost the
        sheet cannot know. The row's `cost` is a list like
        `[{"pay": "tap"}, {"pay": "pay_life", "amount": 2}]`; empty is free.
        """
        for row in (self.of(obj) or {}).get("abilities", []):
            if row.get("ability") == index:
                return row
        return None

    def face(self, obj: Optional[dict], face: Any = "own") -> Optional[dict]:
        """The face a `cast` puts on the stack: the sheet row for `"own"`, its
        `second_face` (an adventure or prepare face) for `"second"`."""
        row = self.of(obj)
        if row is None:
            return None
        return row.get("second_face") if face == "second" else row

    def has_keyword(self, obj: dict, name: str) -> bool:
        """Whether an observed object has keyword `name` right now (from its mask)."""
        bit = self.keyword_bits.get(name)
        return bit is not None and bool(int(obj.get("keywords", 0)) >> bit & 1)

    def keywords(self, obj: dict) -> list[str]:
        mask = int(obj.get("keywords", 0))
        return [n for n, b in self.keyword_bits.items() if mask >> b & 1]


class Action:
    """One offered action. `kind` and `fields` are the stable contract; `label` is debug text."""

    __slots__ = ("id", "kind", "fields", "label", "raw")

    def __init__(self, raw: dict):
        self.raw = raw
        self.id: int = raw.get("id", 0)
        self.label: str = raw.get("label", "")
        structured = raw.get("action") or {}
        self.kind: str = structured.get("action", "")
        self.fields: dict = {k: v for k, v in structured.items() if k != "action"}

    def get(self, field: str, default: Any = None) -> Any:
        """A field of this action (`card`, `targets`, `payment`...), or `default`."""
        return self.fields.get(field, default)

    def __repr__(self) -> str:
        return f"Action(id={self.id}, kind={self.kind!r}, fields={self.fields!r})"


class Decision:
    """One decision: your seat's view, the question, and the offered actions."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.n: int = raw.get("n", 0)
        self.observation: dict = raw.get("observation") or {}
        self.question: dict = raw.get("question") or {}
        self.actions: list[Action] = [Action(a) for a in raw.get("actions", [])]
        self.received = time.monotonic()

    # Convenience views of the observation. All return empty values, never
    # raise, when a field is missing.
    @property
    def hand(self) -> list[dict]:
        return self.observation.get("hand", [])

    @property
    def board(self) -> list[dict]:
        return self.observation.get("board", [])

    @property
    def you(self) -> dict:
        return self.observation.get("you", {})

    @property
    def opponent(self) -> dict:
        return self.observation.get("opponent", {})

    @property
    def seat(self) -> Optional[int]:
        return self.observation.get("seat")

    def mine(self, zone: str = "battlefield") -> list[dict]:
        """Your objects in `zone` (`battlefield`, `graveyard`, `exile`)."""
        return [o for o in self.board if o.get("controller") == self.seat and o.get("zone") == zone]

    def theirs(self, zone: str = "battlefield") -> list[dict]:
        return [o for o in self.board if o.get("controller") != self.seat and o.get("zone") == zone]

    def object(self, instance_id: Any) -> Optional[dict]:
        """The visible object with this instance id (hand, board, revealed, and
        the cards a decision names such as a searched library's), or `None`."""
        for o in (
            self.hand
            + self.board
            + self.observation.get("revealed", [])
            + self.observation.get("decision_objects", [])
        ):
            if o.get("id") == instance_id:
                return o
        return None

    @staticmethod
    def counter(obj: dict, kind: str) -> int:
        """How many `kind` counters (`charge`, `stun`, ...) an object has; 0
        when it has none or the kind is unknown. `+1/+1` and `-1/-1` are
        `plus_counters` and `minus_counters` on the object itself."""
        return int((obj.get("counters") or {}).get(kind, 0))

    @property
    def kind(self) -> str:
        """The question's kind (`priority`, `declare_attackers`, `pick`...).

        A kind you do not know is a question from a newer engine: answer it
        with your default choice, never by exiting."""
        return self.question.get("kind", "")

    @property
    def window(self) -> str:
        """For a `priority` question, when you may act (`precombat_main`,
        `upkeep`, `stack_response`...); `""` otherwise."""
        return self.question.get("window", "") or ""

    def is_main_phase(self) -> bool:
        """True in your own main phases, the only windows where lands,
        creatures and sorceries can be played."""
        return self.window in ("precombat_main", "postcombat_main")

    def of_kind(self, *kinds: str) -> list[Action]:
        return [a for a in self.actions if a.kind in kinds]

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.received) * 1000


class Limits:
    def __init__(self, raw: Optional[dict] = None):
        raw = raw or {}
        self.decision_ms: int = int(raw.get("decision_ms", 5000))
        self.handshake_ms: int = int(raw.get("handshake_ms", 20000))


class Bot:
    """Subclass this. Override `choose`; the other hooks are optional."""

    name = "unnamed-bot"
    version = "0"

    def __init__(self) -> None:
        self.cards = Cards()
        self.limits = Limits()
        self.engine = ""
        self.abi = 0
        self.rng = random.Random(0)

    def hello(self, engine: str, abi: int) -> None:
        """Once per process, before any game. `self.cards` and `self.limits` are set."""

    def start_game(self, seat: int, on_play: bool, seed: int, deck: list[int]) -> None:
        """A new game. `deck` is your own 40-card list (arena ids). Seed your randomness here."""
        self.rng = random.Random(seed)

    def choose(self, decision: Decision) -> "Action | int":
        """Return one of `decision.actions` (or its `id`)."""
        raise NotImplementedError

    def end_game(self, result: str) -> None:
        """`result` is win, loss, draw or capped."""


def _send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _legacy(bot: Bot) -> bool:
    """True when `choose` has the pre-client signature (observation, question, actions)."""
    code = getattr(type(bot).choose, "__code__", None)
    return code is not None and code.co_argcount == 4


def _answer(bot: Bot, raw: dict, legacy: bool) -> int:
    if legacy:
        chosen = bot.choose(raw.get("observation"), raw.get("question"), raw.get("actions", []))  # type: ignore[call-arg]
    else:
        chosen = bot.choose(Decision(raw))
    return chosen.id if isinstance(chosen, Action) else int(chosen)


def run(bot: Bot, lines: Optional[Iterable[str]] = None) -> None:
    """Speak the protocol on stdin/stdout until `bye`. `lines` replaces stdin in tests."""
    legacy = _legacy(bot)
    for line in sys.stdin if lines is None else lines:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        kind = message.get("type")
        if kind == "hello":
            bot.cards = Cards(message.get("cards"))
            bot.limits = Limits(message.get("limits"))
            bot.engine = message.get("engine", "")
            bot.abi = message.get("abi", 0)
            bot.hello(bot.engine, bot.abi)
            _send({"type": "ready", "protocol": PROTOCOL, "name": bot.name, "version": bot.version})
        elif kind == "game_start":
            bot.start_game(message["seat"], message["on_play"], message["seed"], message["deck"])
        elif kind == "decision":
            _send({"type": "action", "n": message["n"], "id": _answer(bot, message, legacy)})
        elif kind == "game_end":
            bot.end_game(message["result"])
        elif kind == "bye":
            return
        # Any other message type is from a newer host: ignore it.

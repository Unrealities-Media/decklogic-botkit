"""Reinforcement-learning environments over the simulator library.

Two shapes, standard library only, following the Gymnasium and PettingZoo
conventions so the usual training loops fit without either package:

* ``SimlibEnv``: one learner seat against a built-in bot (``random``,
  ``beginner``, ``quick``, ``deep``). ``reset`` / ``step`` return what
  ``gymnasium.Env`` returns.
* ``SimlibAEC``: both seats are agents (self-play), with PettingZoo's AEC
  calls (``agent_selection``, ``last``, ``step``, ``agent_iter``).

An observation is a dict: ``decision`` is the protocol's decision message as
parsed JSON (your seat's view, the question, the offered actions; see
``protocol/PROTOCOL.md``), and ``action_mask`` is a list of 0/1 of length
``max_actions`` marking which action indices are offered. An action is an
index into ``decision["actions"]``, never an engine id, so a fixed-size policy
head works. Every offered action is legal; the mask is the whole rule.

The reward is 0 on every step and, when the game ends, +1 for a win, -1 for a
loss and 0 for a draw, from the acting seat's point of view. A game stopped by
the engine's turn cap (``result`` ``"capped"``) is a truncation, not a
termination, with reward 0.

Offers longer than ``max_actions`` (default 128; the longest seen in 30 random
games per pack was 56) keep their first ``max_actions`` entries, which are all
legal, and count the cut in ``info["actions_cut"]``.

If ``gymnasium`` is installed, ``SimlibEnv.gymnasium_spaces()`` returns the
matching ``action_space`` and the mask's space; the decision itself has no
fixed shape, so encode it yourself.
"""

import random
from typing import Iterator, Optional

import simlib


def _reward(over: dict, seat: int) -> float:
    winner = over.get("winner")
    if winner is None:
        return 0.0
    return 1.0 if winner == seat else -1.0


class _Table:
    """One game at a time on one engine, with decks drawn per reset."""

    def __init__(self, engine: "simlib.Engine", decks: Optional[list], max_actions: int, labels: bool):
        if max_actions < 1:
            raise ValueError("max_actions must be at least 1")
        self.engine = engine
        self.decks = decks if decks is not None else [d["main"] for d in engine.decks()]
        if len(self.decks) < 1:
            raise ValueError("the pack has no decks; pass decks=[...]")
        self.max_actions = max_actions
        self.labels = labels
        self.game: Optional["simlib.Game"] = None
        self.decision: Optional[dict] = None
        self.cut = 0

    def new_game(self, seed: int, decks: Optional[tuple]) -> None:
        if self.game is not None:
            self.game.close()
        rng = random.Random(seed)
        pair = list(decks) if decks is not None else [rng.choice(self.decks), rng.choice(self.decks)]
        self.game = self.engine.game(pair, seed=seed, on_play=rng.randrange(2), labels=self.labels)
        self.cut = 0
        self.decision = self.game.decision()

    def observation(self) -> dict:
        offered = len(self.decision.get("actions", ())) if self.decision["type"] == "decision" else 0
        if offered > self.max_actions:
            self.cut += 1
        shown = min(offered, self.max_actions)
        return {"decision": self.decision, "action_mask": [1] * shown + [0] * (self.max_actions - shown)}

    def play_index(self, index: int) -> None:
        actions = self.decision["actions"]
        if not 0 <= index < min(len(actions), self.max_actions):
            raise ValueError(f"action index {index} is not offered ({min(len(actions), self.max_actions)} offered)")
        self.game.apply(actions[index]["id"])
        self.decision = self.game.decision()

    def over(self) -> bool:
        return self.decision["type"] == "over"

    def close(self) -> None:
        if self.game is not None:
            self.game.close()
            self.game = None


class SimlibEnv:
    """One learner seat against a built-in opponent, Gymnasium-style.

    ``seat`` is 0, 1, or ``None`` to alternate seats game by game. ``decks``
    is a list of deck card lists (default: the pack's decks); each reset draws
    two with the reset's seed, or pass ``options={"decks": (a, b)}``.
    """

    metadata = {"render_modes": []}

    def __init__(self, engine: "simlib.Engine", opponent: str = "random", seat: Optional[int] = None,
                 decks: Optional[list] = None, max_actions: int = 128, labels: bool = False,
                 knowledge: Optional[str] = None):
        self.table = _Table(engine, decks, max_actions, labels)
        self.opponent_name = opponent
        self.knowledge = knowledge
        self.fixed_seat = seat
        self.seat = 0 if seat is None else seat
        self.games = 0
        self.opponent: Optional["simlib.Bot"] = None

    @property
    def max_actions(self) -> int:
        return self.table.max_actions

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        seed = random.randrange(2**31) if seed is None else seed
        self.seat = self.games % 2 if self.fixed_seat is None else self.fixed_seat
        self.games += 1
        self.table.new_game(seed, (options or {}).get("decks"))
        if self.opponent is not None:
            self.opponent.close()
        self.opponent = self.table.game.bot(self.opponent_name, 1 - self.seat, seed + 1, knowledge=self.knowledge)
        self._advance()
        return self.table.observation(), self._info()

    def step(self, action: int):
        if self.table.over():
            raise RuntimeError("the game is over; call reset()")
        self.table.play_index(int(action))
        self._advance()
        done = self.table.over()
        capped = done and self.table.decision.get("result") == "capped"
        reward = _reward(self.table.decision, self.seat) if done else 0.0
        return self.table.observation(), reward, done and not capped, capped, self._info()

    def _advance(self) -> None:
        # The opponent answers its own decisions until the learner is asked.
        while not self.table.over() and self.table.decision["seat"] != self.seat:
            self.table.game.apply(self.opponent.choose())
            self.table.decision = self.table.game.decision()

    def _info(self) -> dict:
        info = {"seat": self.seat, "actions_cut": self.table.cut}
        if self.table.over():
            info["result"] = self.table.decision
        return info

    def gymnasium_spaces(self):
        """``(action_space, action_mask_space)`` as gymnasium spaces."""
        from gymnasium import spaces
        return spaces.Discrete(self.max_actions), spaces.MultiBinary(self.max_actions)

    def close(self) -> None:
        if self.opponent is not None:
            self.opponent.close()
            self.opponent = None
        self.table.close()


class SimlibAEC:
    """Both seats as agents ``seat_0`` and ``seat_1``, PettingZoo AEC-style.

    Only the agent named by ``agent_selection`` acts. When the game ends
    (terminated, or truncated by the turn cap), each agent is stepped once
    more with ``None`` (PettingZoo's dead step)
    after reading its final reward from ``last()``; then ``agents`` is empty.
    """

    possible_agents = ["seat_0", "seat_1"]
    metadata = {"render_modes": [], "is_parallelizable": False}

    def __init__(self, engine: "simlib.Engine", decks: Optional[list] = None, max_actions: int = 128,
                 labels: bool = False):
        self.table = _Table(engine, decks, max_actions, labels)
        self.agents: list = []
        self.rewards: dict = {}
        self._cumulative_rewards: dict = {}
        self.terminations: dict = {}
        self.truncations: dict = {}
        self.infos: dict = {}
        self.agent_selection: Optional[str] = None

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> None:
        seed = random.randrange(2**31) if seed is None else seed
        self.table.new_game(seed, (options or {}).get("decks"))
        self.agents = list(self.possible_agents)
        for name in ("rewards", "_cumulative_rewards"):
            setattr(self, name, {a: 0.0 for a in self.agents})
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}
        self._select()

    def observe(self, agent: str) -> dict:
        obs = self.table.observation()
        if self.table.over() or self.possible_agents.index(agent) == self.table.decision["seat"]:
            return obs
        # Not this agent's turn: no decision of its own to show.
        return {"decision": None, "action_mask": [0] * self.table.max_actions}

    def last(self, observe: bool = True):
        agent = self.agent_selection
        return (self.observe(agent) if observe else None, self._cumulative_rewards[agent],
                self.terminations[agent], self.truncations[agent], self.infos[agent])

    def step(self, action: Optional[int]) -> None:
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            if action is not None:
                raise ValueError("a finished agent is stepped with None")
            self.agents.remove(agent)
            del self._cumulative_rewards[agent]
            self.agent_selection = self.agents[0] if self.agents else None
            return
        self._cumulative_rewards[agent] = 0.0
        self.table.play_index(int(action))
        if self.table.over():
            over = self.table.decision
            capped = over.get("result") == "capped"
            for i, a in enumerate(self.possible_agents):
                self.rewards[a] = _reward(over, i)
                self._cumulative_rewards[a] = self.rewards[a]
                self.terminations[a] = not capped
                self.truncations[a] = capped
                self.infos[a] = {"result": over, "actions_cut": self.table.cut}
        self._select()

    def _select(self) -> None:
        if self.table.over():
            self.agent_selection = self.agents[0] if self.agents else None
        else:
            self.agent_selection = self.possible_agents[self.table.decision["seat"]]

    def agent_iter(self, max_iter: int = 2**63) -> Iterator[str]:
        for _ in range(max_iter):
            if not self.agents:
                return
            yield self.agent_selection

    def close(self) -> None:
        self.table.close()

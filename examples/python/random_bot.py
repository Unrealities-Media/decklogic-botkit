"""The smallest possible bot: a uniformly random legal action."""

import botlib


class RandomBot(botlib.Bot):
    name = "py-random"
    version = "1"

    def choose(self, decision):
        return self.rng.choice(decision.actions)


if __name__ == "__main__":
    botlib.run(RandomBot())

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .bots import BotController, Difficulty
from .game import Game, GameState, TurnPhase
from .models import Player, PlayerType


@dataclass(frozen=True, slots=True)
class SoloConfig:
    bot_count: int
    difficulty: Difficulty
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        if self.bot_count not in (1, 2, 3):
            raise ValueError("Una partida Solo debe tener 1, 2 o 3 bots")


class SoloSession:
    """Orchestrates human + bot turns without owning game rules.

    Game remains the sole authority. This class only decides who acts next and
    delegates bot decisions through BotController.
    """

    def __init__(self, config: SoloConfig, human_name: str = "Mar") -> None:
        self.config = config
        rng = random.Random(config.seed)
        players = [Player("human", human_name, PlayerType.HUMAN)]
        for i in range(config.bot_count):
            players.append(Player(f"bot{i+1}", f"Bot {i+1}", PlayerType.BOT))

        self.game = Game(players, seed=rng.randrange(1 << 30))
        self.controllers = {
            p.id: BotController(config.difficulty, seed=rng.randrange(1 << 30))
            for p in players[1:]
        }
        self.game.start()

    @property
    def human_id(self) -> str:
        return "human"

    @property
    def human_turn(self) -> bool:
        return self.game.state == GameState.PLAYING and self.game.current_player.id == self.human_id

    def play_next_bot(self):
        """Execute exactly one bot turn and return its BotAction.

        Keeping one turn per call lets the GUI animate and repaint between bots.
        """
        if self.game.state != GameState.PLAYING or self.human_turn:
            return None
        player_id = self.game.current_player.id
        controller = self.controllers[player_id]
        return controller.play_turn(self.game, player_id)

    def is_over(self) -> bool:
        return self.game.state == GameState.WON

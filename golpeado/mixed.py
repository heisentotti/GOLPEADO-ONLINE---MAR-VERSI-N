from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .bots import BotController, Difficulty
from .game import Game, GameState
from .models import Player, PlayerType


@dataclass(frozen=True, slots=True)
class MixedConfig:
    human_count: int
    bot_count: int
    difficulty: Difficulty
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        if self.human_count not in (1, 2, 3):
            raise ValueError("El modo mixto admite 1, 2 o 3 humanos")
        if self.bot_count not in (1, 2, 3):
            raise ValueError("El modo mixto admite 1, 2 o 3 bots")
        if self.human_count + self.bot_count > 4:
            raise ValueError("La partida no puede superar 4 jugadores")
        if self.human_count + self.bot_count < 2:
            raise ValueError("Se necesitan al menos 2 jugadores")


class MixedSession:
    """Human + bot orchestration on top of the same authoritative Game."""

    def __init__(self, config: MixedConfig, human_names: Optional[list[str]] = None) -> None:
        self.config = config
        rng = random.Random(config.seed)
        names = human_names or [f"Jugador {i + 1}" for i in range(config.human_count)]
        if len(names) != config.human_count:
            raise ValueError("La cantidad de nombres humanos no coincide")

        players = [Player(f"human{i + 1}", names[i], PlayerType.HUMAN) for i in range(config.human_count)]
        for i in range(config.bot_count):
            players.append(Player(f"bot{i + 1}", f"Bot {i + 1}", PlayerType.BOT))

        self.game = Game(players, seed=rng.randrange(1 << 30))
        self.controllers = {
            p.id: BotController(config.difficulty, seed=rng.randrange(1 << 30))
            for p in players if p.type == PlayerType.BOT
        }
        self.game.start()

    @property
    def human_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.game.players if p.type == PlayerType.HUMAN)

    @property
    def bot_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.game.players if p.type == PlayerType.BOT)

    def human_turn(self, player_id: str) -> bool:
        return self.game.state == GameState.PLAYING and self.game.current_player.id == player_id

    def play_next_bot(self):
        if self.game.state != GameState.PLAYING:
            return None
        pid = self.game.current_player.id
        if pid not in self.controllers:
            return None
        return self.controllers[pid].play_turn(self.game, pid)

    def run_bots_until_human_or_end(self, max_turns: int = 1000) -> int:
        turns = 0
        while turns < max_turns and self.game.state == GameState.PLAYING and self.game.current_player.id in self.controllers:
            self.play_next_bot()
            turns += 1
        return turns

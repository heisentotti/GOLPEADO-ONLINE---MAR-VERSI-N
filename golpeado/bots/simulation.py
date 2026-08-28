from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import random
from typing import Iterable

from ..game import Game, GameState
from ..models import Player, PlayerType
from .controller import BotController
from .strategy import Difficulty


@dataclass(frozen=True, slots=True)
class SimulationStats:
    games: int
    completed: int
    wins_by_difficulty: dict[str, int]
    wins_by_player: dict[str, int]
    victory_reasons: dict[str, int]
    total_turns: int
    max_turns: int
    illegal_moves: int
    invariant_failures: int
    impossible_states: int
    stalled_games: int

    @property
    def completion_rate(self) -> float:
        return self.completed / self.games if self.games else 0.0

    @property
    def average_turns(self) -> float:
        return self.total_turns / self.completed if self.completed else 0.0


def simulate(
    games: int = 1000,
    player_count: int = 4,
    difficulties: Iterable[Difficulty | str] | None = None,
    seed: int = 1000,
    max_turns: int = 2000,
) -> SimulationStats:
    if not 2 <= player_count <= 4:
        raise ValueError("player_count debe estar entre 2 y 4")
    difficulties = list(difficulties or [Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.EXPERT])
    if len(difficulties) != player_count:
        raise ValueError("Debe proporcionarse una dificultad por jugador")

    wins_by_difficulty = Counter()
    wins_by_player = Counter()
    victory_reasons = Counter()
    illegal_moves = invariant_failures = impossible_states = stalled_games = 0
    completed = total_turns = 0
    maximum_seen = 0

    for game_no in range(games):
        rng = random.Random(seed + game_no)
        players = [Player(f"p{i}", f"Bot {i+1}", PlayerType.BOT) for i in range(player_count)]
        game = Game(players, seed=seed + game_no)
        game.start()
        controllers = [BotController(difficulties[i], seed=rng.randrange(1 << 30)) for i in range(player_count)]

        turns = 0
        while game.state == GameState.PLAYING and turns < max_turns:
            current = game.current_player
            controller = controllers[game.current_index]
            try:
                controller.play_turn(game, current.id)
                game._assert_invariants()
                _assert_no_impossible_state(game)
            except Exception as exc:
                # Simulation failures are counted separately; re-raising would
                # stop a long statistical run and hide the aggregate result.
                if exc.__class__.__name__ in {"InvalidMove", "GameOver"}:
                    illegal_moves += 1
                elif isinstance(exc, RuntimeError) and "Invariante rota" in str(exc):
                    invariant_failures += 1
                else:
                    impossible_states += 1
                break
            turns += 1

        maximum_seen = max(maximum_seen, turns)
        total_turns += turns
        if game.state == GameState.WON:
            completed += 1
            wins_by_player[game.winner.player_id] += 1
            winner_index = next(i for i, p in enumerate(players) if p.id == game.winner.player_id)
            wins_by_difficulty[str(Difficulty(difficulties[winner_index]).value)] += 1
            victory_reasons[game.winner.reason] += 1
        elif turns >= max_turns:
            stalled_games += 1

    return SimulationStats(
        games=games,
        completed=completed,
        wins_by_difficulty=dict(wins_by_difficulty),
        wins_by_player=dict(wins_by_player),
        victory_reasons=dict(victory_reasons),
        total_turns=total_turns,
        max_turns=maximum_seen,
        illegal_moves=illegal_moves,
        invariant_failures=invariant_failures,
        impossible_states=impossible_states,
        stalled_games=stalled_games,
    )


def _assert_no_impossible_state(game: Game) -> None:
    all_cards = []
    all_cards.extend(game.deck.cards)
    all_cards.extend(game.discard_pile)
    for player in game.players:
        all_cards.extend(player.hand)
        if player.lowered_group:
            all_cards.extend(player.lowered_group.cards)
        if player.plug:
            if not player.has_card(player.plug.card.id):
                raise AssertionError("Un enchufe no pertenece a la mano de su dueño")
    ids = [c.id for c in all_cards]
    if len(ids) != len(set(ids)):
        raise AssertionError("Carta física duplicada en el estado")

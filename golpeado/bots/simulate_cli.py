from .simulation import simulate
from .strategy import Difficulty


def main() -> None:
    stats = simulate(1000, 4, [Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.EXPERT], seed=260826, max_turns=5000)
    print(f"games={stats.games}")
    print(f"completed={stats.completed}")
    print(f"completion_rate={stats.completion_rate:.3f}")
    print(f"average_turns={stats.average_turns:.1f}")
    print(f"max_turns={stats.max_turns}")
    print(f"illegal_moves={stats.illegal_moves}")
    print(f"impossible_states={stats.impossible_states}")
    print(f"stalled_games={stats.stalled_games}")
    print(f"wins_by_difficulty={stats.wins_by_difficulty}")
    print(f"victory_reasons={stats.victory_reasons}")


if __name__ == "__main__":
    main()

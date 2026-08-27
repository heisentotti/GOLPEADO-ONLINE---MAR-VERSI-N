from golpeado.solo import SoloConfig, SoloSession
from golpeado import GameState
from golpeado.bots import Difficulty


def test_solo_config_rejects_invalid_bot_count():
    for count in (0, 4, 5):
        try:
            SoloConfig(count, Difficulty.EASY)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid bot count accepted")


def test_solo_runs_until_human_turn_or_win_without_manual_intervention():
    for difficulty in Difficulty:
        session = SoloSession(SoloConfig(3, difficulty, seed=2026))
        for _ in range(3000):
            if session.is_over() or session.human_turn:
                break
            session.play_next_bot()
        assert session.game.state in (GameState.PLAYING, GameState.WON)
        assert session.game.current_player.id == "human" or session.game.state == GameState.WON


def test_solo_all_bot_counts_and_difficulties_reach_human_turn_or_win():
    for count in (1, 2, 3):
        for difficulty in Difficulty:
            session = SoloSession(SoloConfig(count, difficulty, seed=7000 + count * 10 + list(Difficulty).index(difficulty)))
            for _ in range(10000):
                if session.is_over() or session.human_turn:
                    break
                session.play_next_bot()
            assert session.is_over() or session.human_turn

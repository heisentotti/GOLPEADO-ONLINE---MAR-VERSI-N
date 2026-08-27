import pytest

from golpeado import GameState
from golpeado.bots import Difficulty
from golpeado.mixed import MixedConfig, MixedSession


@pytest.mark.parametrize("humans,bots", [(1,1),(1,2),(1,3),(2,1),(2,2),(3,1)])
def test_all_official_mixed_compositions_start(humans, bots):
    s = MixedSession(MixedConfig(humans, bots, Difficulty.NORMAL, seed=100 + humans * 10 + bots))
    assert len(s.game.players) == humans + bots
    assert sum(p.type.value == "human" for p in s.game.players) == humans
    assert sum(p.type.value == "bot" for p in s.game.players) == bots
    assert s.game.state == GameState.PLAYING


def test_mixed_rejects_invalid_compositions():
    with pytest.raises(ValueError): MixedConfig(0, 2, Difficulty.EASY)
    with pytest.raises(ValueError): MixedConfig(2, 3, Difficulty.EASY)
    with pytest.raises(ValueError): MixedConfig(1, 0, Difficulty.EASY)


@pytest.mark.parametrize("humans,bots", [(1,1),(1,2),(1,3),(2,1),(2,2),(3,1)])
def test_mixed_bots_run_until_human_or_win(humans, bots):
    s = MixedSession(MixedConfig(humans, bots, Difficulty.EXPERT, seed=5000 + humans * 10 + bots))
    for _ in range(10000):
        if s.game.state == GameState.WON or s.game.current_player.id in s.human_ids:
            break
        s.play_next_bot()
    assert s.game.state in (GameState.PLAYING, GameState.WON)
    assert s.game.state == GameState.WON or s.game.current_player.id in s.human_ids

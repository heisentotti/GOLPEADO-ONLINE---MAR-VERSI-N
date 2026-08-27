import asyncio
import pytest

from golpeado.game import GameState, InvalidMove, TurnPhase
from golpeado.models import PlayerType
from golpeado.online import RoomManager
from golpeado.bots import Difficulty


def run(coro):
    return asyncio.run(coro)


def setup(humans, bots):
    async def go():
        m = RoomManager()
        first = await m.create_room("Host")
        ids = [first]
        for name in ["B", "C"][:humans - 1]:
            ids.append(await m.join_room(first["room_code"], name))
        await m.start_room(first["room_code"], first["player_id"], seed=42, bot_count=bots, bot_difficulty=Difficulty.EXPERT)
        return m, ids
    return run(go())


@pytest.mark.parametrize("humans,bots", [(1,1),(1,2),(1,3),(2,1),(2,2),(3,1)])
def test_official_mixed_online_compositions(humans, bots):
    m, ids = setup(humans, bots)
    room = m.rooms[ids[0]["room_code"]]
    assert len(room.game.players) == humans + bots
    assert sum(p.type == PlayerType.HUMAN for p in room.game.players) == humans
    assert sum(p.type == PlayerType.BOT for p in room.game.players) == bots
    assert room.game.state in (GameState.PLAYING, GameState.WON)
    for x in ids:
        view = m.view_for(room, x["player_id"])
        me = next(p for p in view["players"] if p["id"] == x["player_id"])
        assert me["hand"] is not None
        for other in view["players"]:
            if other["id"] != x["player_id"]:
                assert other["hand"] is None
                assert other["plug"] is None


def test_mixed_online_bots_never_get_other_private_information():
    m, ids = setup(2, 2)
    room = m.rooms[ids[0]["room_code"]]
    bot = next(p for p in room.game.players if p.type == PlayerType.BOT)
    obs = room.bot_controllers[bot.id].observe(room.game, bot.id)
    assert hasattr(obs, "own_hand")
    assert not hasattr(obs, "other_hands")
    assert not hasattr(obs, "other_plugs")
    assert not hasattr(obs, "deck")


def test_human_disconnect_does_not_remove_human_from_mixed_game():
    m, ids = setup(2, 1)
    room = m.rooms[ids[0]["room_code"]]
    human = ids[1]["player_id"]
    run(m.disconnect(room.code, human))
    assert human in room.game.active_player_ids
    state = run(m.reconnect(room.code, human, ids[1]["reconnect_token"], object()))
    assert state["game_state"] == GameState.PLAYING.value or state["game_state"] == GameState.WON.value


def test_mixed_online_rejects_over_capacity():
    async def go():
        m = RoomManager(); a = await m.create_room("A")
        b = await m.join_room(a["room_code"], "B")
        with pytest.raises(InvalidMove):
            await m.start_room(a["room_code"], a["player_id"], bot_count=3)
    run(go())

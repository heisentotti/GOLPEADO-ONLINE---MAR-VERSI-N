
import asyncio
from golpeado.game import GameState, Victory, InvalidMove
from golpeado.online import RoomManager

def run(coro):
    return asyncio.run(coro)

def setup():
    async def go():
        m=RoomManager()
        a=await m.create_room("Mar")
        b=await m.join_room(a["room_code"],"Carlos")
        await m.start_room(a["room_code"],a["player_id"],seed=123)
        return m,a,b
    return run(go())

def test_username_is_exposed_and_stats_start_at_zero():
    m,a,b=setup()
    room=m.rooms[a["room_code"]]
    view=m.view_for(room,a["player_id"])
    names={p["name"] for p in view["players"]}
    assert names=={"Mar","Carlos"}
    assert view["stats"][a["player_id"]]=={"wins":0,"losses":0}
    assert view["stats"][b["player_id"]]=={"wins":0,"losses":0}

def test_chat_is_room_scoped_and_limited():
    m,a,b=setup()
    room=m.rooms[a["room_code"]]
    async def go():
        await m.chat_message(room.code,a["player_id"],"Hola")
    run(go())
    view=m.view_for(room,b["player_id"])
    assert view["chat"][-1]["name"]=="Mar"
    assert view["chat"][-1]["text"]=="Hola"
    with __import__("pytest").raises(InvalidMove):
        run(m.chat_message(room.code,a["player_id"],"x"*301))

def test_revenge_requires_all_active_players_and_resets_game():
    m,a,b=setup()
    room=m.rooms[a["room_code"]]
    old_game=room.game
    old_players=[p.id for p in room.players]
    winner=old_players[0]
    old_game.state=GameState.WON
    old_game.winner=Victory(winner,"test")
    async def go():
        await m.request_revenge(room.code,a["player_id"])
        assert room.game is old_game
        assert room.revenge_votes=={a["player_id"]}
        await m.request_revenge(room.code,b["player_id"])
    run(go())
    assert room.game is not old_game
    assert [p.id for p in room.players]==old_players
    assert room.game.state==GameState.PLAYING
    assert room.revenge_votes==set()

def test_stats_are_recorded_once_when_game_finishes():
    m,a,b=setup()
    room=m.rooms[a["room_code"]]
    room.game.state=GameState.WON
    room.game.winner=Victory(a["player_id"],"test")
    first=m.view_for(room,a["player_id"])
    second=m.view_for(room,a["player_id"])
    assert first["stats"][a["player_id"]]=={"wins":1,"losses":0}
    assert first["stats"][b["player_id"]]=={"wins":0,"losses":1}
    assert second["stats"][a["player_id"]]=={"wins":1,"losses":0}

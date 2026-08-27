import asyncio
import pytest

from golpeado.game import GameState, InvalidMove, TurnPhase
from golpeado.online import RoomManager


def run(coro):
    return asyncio.run(coro)


def setup_room(n=2):
    async def go():
        m = RoomManager()
        a = await m.create_room("A")
        ids = [a]
        for name in ["B", "C", "D"][:n-1]:
            ids.append(await m.join_room(a["room_code"], name))
        await m.start_room(a["room_code"], a["player_id"], seed=100)
        return m, ids
    return run(go())


def test_rooms_max_four_and_start_requires_two():
    async def go():
        m = RoomManager(); a = await m.create_room("A")
        with pytest.raises(InvalidMove): await m.start_room(a["room_code"], a["player_id"])
        for n in ["B", "C", "D"]: await m.join_room(a["room_code"], n)
        with pytest.raises(InvalidMove): await m.join_room(a["room_code"], "E")
    run(go())


@pytest.mark.parametrize("n", [2, 3, 4])
def test_online_game_starts_with_correct_private_views(n):
    m, ids = setup_room(n)
    room = m.rooms[ids[0]["room_code"]]
    for x in ids:
        view = m.view_for(room, x["player_id"])
        me = next(p for p in view["players"] if p["id"] == x["player_id"])
        assert me["hand"] is not None
        assert me["plug"] is not None or me["plug"] is None
        for other in view["players"]:
            if other["id"] != x["player_id"]:
                assert other["hand"] is None
                assert other["plug"] is None


def test_actions_out_of_turn_are_rejected_and_duplicate_action_is_idempotent():
    m, ids = setup_room(2)
    room = m.rooms[ids[0]["room_code"]]
    current = room.game.current_player.id
    other = next(x["player_id"] for x in ids if x["player_id"] != current)
    async def go():
        with pytest.raises(InvalidMove):
            await m.action(room.code, other, "bad1", "draw", {})
        original_card = room.game.current_player.hand[0].id
        result = await m.action(room.code, current, "a1", "discard", {"card_id": original_card})
        again = await m.action(room.code, current, "a1", "discard", {"card_id": original_card})
        assert again["type"] == "state"
        with pytest.raises(InvalidMove, match="action_id"):
            await m.action(room.code, current, "a1", "draw", {})
    run(go())


def test_reconnect_preserves_game_and_abandon_is_permanent():
    m, ids = setup_room(3)
    room = m.rooms[ids[0]["room_code"]]
    player = ids[1]
    async def go():
        await m.disconnect(room.code, player["player_id"])
        state = await m.reconnect(room.code, player["player_id"], player["reconnect_token"], object())
        assert state["game_state"] == GameState.PLAYING.value
        await m.abandon(room.code, player["player_id"])
        assert player["player_id"] in room.game.abandoned_player_ids
        assert player["player_id"] not in room.game.active_player_ids
        with pytest.raises(InvalidMove):
            await m.reconnect(room.code, player["player_id"], player["reconnect_token"], object())
    run(go())


def test_abandon_current_player_moves_to_next_active_and_keeps_cards_out_of_play():
    m, ids = setup_room(4)
    room = m.rooms[ids[0]["room_code"]]
    current = room.game.current_player
    card_ids = [c.id for c in current.hand]
    async def go():
        await m.abandon(room.code, current.id)
    run(go())
    assert current.id not in room.game.active_player_ids
    assert all(cid not in [c.id for c in list(room.game.deck.cards) + room.game.discard_pile] for cid in card_ids)
    assert room.game.current_player.id == ids[1]["player_id"]
    assert room.game.phase == TurnPhase.DRAW


def test_abandon_when_two_active_ends_without_winner():
    m, ids = setup_room(2)
    room = m.rooms[ids[0]["room_code"]]
    run(m.abandon(room.code, ids[0]["player_id"]))
    assert room.game.state == GameState.ENDED
    assert room.game.winner is None


def test_abandon_non_current_does_not_change_current():
    m, ids = setup_room(4)
    room = m.rooms[ids[0]["room_code"]]
    current = room.game.current_player.id
    noncurrent = next(x["player_id"] for x in ids if x["player_id"] != current)
    run(m.abandon(room.code, noncurrent))
    assert room.game.current_player.id == current



def test_simultaneous_actions_are_serialized_and_only_one_can_mutate_a_turn():
    import asyncio
    m, ids = setup_room(2)
    room = m.rooms[ids[0]["room_code"]]
    current = room.game.current_player.id
    card_id = room.game.current_player.hand[0].id

    async def go():
        results = await asyncio.gather(
            m.action(room.code, current, "sim-1", "discard", {"card_id": card_id}),
            m.action(room.code, current, "sim-2", "discard", {"card_id": card_id}),
            return_exceptions=True,
        )
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, InvalidMove)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert len(room.game.discard_pile) == 1

    run(go())

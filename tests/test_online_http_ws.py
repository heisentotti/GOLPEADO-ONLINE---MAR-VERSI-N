import pytest
from fastapi.testclient import TestClient

from golpeado.online import RoomManager, create_app


def test_http_room_lifecycle_and_websocket_protocol():
    manager = RoomManager()
    app = create_app(manager)
    client = TestClient(app)

    a = client.post('/rooms', json={'name': 'Alice'}).json()
    b = client.post(f"/rooms/{a['room_code']}/join", json={'name': 'Bob'}).json()
    assert client.get('/health').json() == {'ok': True}
    assert client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id'], 'seed': 9}).status_code == 200

    with client.websocket_connect(f"/ws/{a['room_code']}") as ws_a:
        ws_a.send_json({'type': 'hello', 'player_id': a['player_id'], 'reconnect_token': a['reconnect_token']})
        state = ws_a.receive_json()['state']
        me = next(p for p in state['players'] if p['id'] == a['player_id'])
        other = next(p for p in state['players'] if p['id'] == b['player_id'])
        assert me['hand'] is not None
        assert other['hand'] is None
        assert other['plug'] is None
        ws_a.send_json({'type': 'ping'})
        assert ws_a.receive_json()['type'] == 'pong'


def test_websocket_rejects_bad_action_without_closing_connection():
    manager = RoomManager(); app = create_app(manager); client = TestClient(app)
    a = client.post('/rooms', json={'name': 'A'}).json()
    b = client.post(f"/rooms/{a['room_code']}/join", json={'name': 'B'}).json()
    client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id'], 'seed': 3})
    with client.websocket_connect(f"/ws/{a['room_code']}") as ws:
        ws.send_json({'type': 'hello', 'player_id': b['player_id'], 'reconnect_token': b['reconnect_token']})
        ws.receive_json()
        ws.send_json({'type': 'action', 'action_id': 'illegal', 'action': 'draw', 'payload': {}})
        error = ws.receive_json()
        assert error['type'] == 'error'
        ws.send_json({'type': 'ping'})
        assert ws.receive_json()['type'] == 'pong'


def test_reconnected_socket_invalidates_stale_socket_and_stale_close_cannot_disconnect_new_socket():
    manager = RoomManager(); app = create_app(manager); client = TestClient(app)
    a = client.post('/rooms', json={'name': 'A'}).json()
    b = client.post(f"/rooms/{a['room_code']}/join", json={'name': 'B'}).json()
    client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id']})
    with client.websocket_connect(f"/ws/{a['room_code']}") as ws_old:
        ws_old.send_json({'type': 'hello', 'player_id': a['player_id'], 'reconnect_token': a['reconnect_token']})
        ws_old.receive_json()
        with client.websocket_connect(f"/ws/{a['room_code']}") as ws_new:
            ws_new.send_json({'type': 'hello', 'player_id': a['player_id'], 'reconnect_token': a['reconnect_token']})
            ws_new.receive_json()
            ws_old.send_json({'type': 'action', 'action_id': 'stale', 'action': 'draw', 'payload': {}})
            error = ws_old.receive_json()
            assert error['type'] == 'error'
            assert error['message'] == 'Conexión no autorizada'
            room = manager.rooms[a['room_code']]
            assert room.connections[a['player_id']].connected is True
            ws_new.send_json({'type': 'ping'})
            assert ws_new.receive_json()['type'] == 'pong'


def test_http_start_never_accepts_client_supplied_seed():
    manager = RoomManager(); app = create_app(manager); client = TestClient(app)
    a = client.post('/rooms', json={'name': 'A'}).json()
    client.post(f"/rooms/{a['room_code']}/join", json={'name': 'B'})
    captured = {}
    original = manager.start_room

    async def wrapped(code, requester_id, seed=None, bot_count=0, bot_difficulty='normal'):
        captured['seed'] = seed
        return await original(code, requester_id, seed=seed, bot_count=bot_count, bot_difficulty=bot_difficulty)

    manager.start_room = wrapped
    response = client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id'], 'seed': 123456789})
    assert response.status_code == 200
    assert captured['seed'] is None


def test_websocket_ignores_client_state_mutation_fields():
    manager = RoomManager(); app = create_app(manager); client = TestClient(app)
    a = client.post('/rooms', json={'name': 'A'}).json()
    b = client.post(f"/rooms/{a['room_code']}/join", json={'name': 'B'}).json()
    client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id']})
    room = manager.rooms[a['room_code']]
    before = [c.id for c in room.game.players[0].hand]
    with client.websocket_connect(f"/ws/{a['room_code']}") as ws:
        ws.send_json({'type': 'hello', 'player_id': a['player_id'], 'reconnect_token': a['reconnect_token']})
        ws.receive_json()
        ws.send_json({'type': 'action', 'action_id': 'evil', 'action': 'draw', 'payload': {
            'hand': ['FAKE'], 'turn_number': 999999, 'winner': {'player_id': a['player_id']},
            'cards': ['FAKE'], 'plug': {'card': 'FAKE'}
        }})
        ws.receive_json()
    assert before == [c.id for c in room.game.players[0].hand]


def test_websocket_rejects_unknown_message_without_closing_connection():
    manager = RoomManager(); app = create_app(manager); client = TestClient(app)
    a = client.post('/rooms', json={'name': 'A'}).json()
    b = client.post(f"/rooms/{a['room_code']}/join", json={'name': 'B'}).json()
    client.post(f"/rooms/{a['room_code']}/start", json={'player_id': a['player_id']})
    with client.websocket_connect(f"/ws/{a['room_code']}") as ws:
        ws.send_json({'type': 'hello', 'player_id': a['player_id'], 'reconnect_token': a['reconnect_token']})
        ws.receive_json()
        ws.send_json({'type': 'not_a_real_message'})
        error = ws.receive_json()
        assert error['type'] == 'error'
        ws.send_json({'type': 'ping'})
        assert ws.receive_json()['type'] == 'pong'

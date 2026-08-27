from __future__ import annotations

import asyncio
import json
import secrets
import string
from dataclasses import dataclass, field
from typing import Any, Optional

from .game import Game, GameOver, GameState, InvalidMove, TurnPhase
from .models import Player, PlayerType
from .bots import BotController, Difficulty


def _code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@dataclass
class Connection:
    player_id: str
    token: str
    websocket: Any = None
    connected: bool = False
    seen_actions: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=dict)


@dataclass
class Room:
    code: str
    host_id: str
    players: list[Player]
    connections: dict[str, Connection]
    game: Optional[Game] = None
    started: bool = False
    bot_count: int = 0
    bot_difficulty: Difficulty = Difficulty.NORMAL
    bot_controllers: dict[str, BotController] = field(default_factory=dict)
    chat: list[dict[str, Any]] = field(default_factory=list)
    revenge_votes: set[str] = field(default_factory=set)

    @property
    def active_count(self) -> int:
        if self.game is None:
            return len(self.players)
        return len(self.game.active_player_ids)


class RoomManager:
    """Authoritative room/session layer around the existing Game engine."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.player_stats: dict[str, dict[str, int]] = {}
        self._lock = asyncio.Lock()

    async def create_room(self, name: str) -> dict[str, Any]:
        async with self._lock:
            player_id = secrets.token_hex(8)
            token = secrets.token_urlsafe(24)
            player = Player(player_id, name, PlayerType.HUMAN)
            code = _code()
            while code in self.rooms:
                code = _code()
            room = Room(code, player_id, [player], {player_id: Connection(player_id, token)})
            self.rooms[code] = room
            self.player_stats[player_id] = {"wins": 0, "losses": 0}
            return {"room_code": code, "player_id": player_id, "reconnect_token": token, "host": True}

    async def join_room(self, code: str, name: str) -> dict[str, Any]:
        async with self._lock:
            room = self.rooms.get(code.upper())
            if room is None:
                raise InvalidMove("Sala inexistente")
            if room.started:
                raise InvalidMove("La partida ya comenzó")
            if len(room.players) >= 4:
                raise InvalidMove("La sala está llena")
            player_id = secrets.token_hex(8)
            token = secrets.token_urlsafe(24)
            room.players.append(Player(player_id, name, PlayerType.HUMAN))
            room.connections[player_id] = Connection(player_id, token)
            self.player_stats[player_id] = {"wins": 0, "losses": 0}
            return {"room_code": room.code, "player_id": player_id, "reconnect_token": token, "host": False}

    async def start_room(
        self, code: str, requester_id: str, seed: Optional[int] = None,
        bot_count: int = 0, bot_difficulty: Difficulty | str = Difficulty.NORMAL,
    ) -> None:
        async with self._lock:
            room = self._room(code)
            if requester_id != room.host_id:
                raise InvalidMove("Solo el anfitrión puede iniciar la partida")
            if room.started:
                raise InvalidMove("La partida ya comenzó")
            bot_count = int(bot_count)
            if bot_count < 0 or bot_count > 3:
                raise InvalidMove("Cantidad de bots inválida")
            if len(room.players) + bot_count < 2:
                raise InvalidMove("Se necesitan al menos 2 jugadores")
            if len(room.players) + bot_count > 4:
                raise InvalidMove("La partida no puede superar 4 jugadores")
            if len(room.players) > 3 and bot_count:
                raise InvalidMove("No hay espacio para esos bots")

            difficulty = Difficulty(bot_difficulty)
            room.bot_count = bot_count
            room.bot_difficulty = difficulty
            for i in range(bot_count):
                bot_id = f"bot-{secrets.token_hex(6)}"
                bot = Player(bot_id, f"Bot {i + 1}", PlayerType.BOT)
                room.players.append(bot)
                room.connections[bot_id] = Connection(bot_id, "", None, False)
                room.bot_controllers[bot_id] = BotController(difficulty, seed=secrets.randbits(30))

            # Client-facing HTTP/WebSocket callers must not control the deck
            # seed. The optional seed remains available to trusted tests/local
            # orchestration through RoomManager, but the HTTP route never passes it.
            if seed is None:
                seed = secrets.randbits(64)
            room.game = Game(room.players, seed=seed)
            room.game.start()
            room.started = True
            await self._run_bots_locked(room)

    async def reconnect(self, code: str, player_id: str, token: str, websocket: Any) -> dict[str, Any]:
        async with self._lock:
            room = self._room(code)
            conn = room.connections.get(player_id)
            if conn is None or not secrets.compare_digest(conn.token, token):
                raise InvalidMove("Credenciales de reconexión inválidas")
            if room.game and player_id in room.game.abandoned_player_ids:
                raise InvalidMove("El jugador abandonó definitivamente la partida")
            conn.websocket = websocket
            conn.connected = True
            return self.view_for(room, player_id)

    async def attach(self, code: str, player_id: str, token: str, websocket: Any) -> dict[str, Any]:
        return await self.reconnect(code, player_id, token, websocket)

    async def disconnect(self, code: str, player_id: str, websocket: Any = None) -> None:
        async with self._lock:
            room = self._room(code)
            conn = room.connections.get(player_id)
            if conn is None:
                return
            # A stale socket must never be allowed to tear down a newer
            # authenticated connection after a reconnect.
            if websocket is not None and conn.websocket is not websocket:
                return
            conn.connected = False
            conn.websocket = None

    async def abandon(self, code: str, player_id: str) -> None:
        async with self._lock:
            room = self._room(code)
            if room.game is None or not room.started:
                raise InvalidMove("La partida no ha comenzado")
            room.game.abandon(player_id)
            conn = room.connections.get(player_id)
            if conn:
                conn.connected = False
                conn.websocket = None

    async def action(self, code: str, player_id: str, action_id: str, action: str, payload: dict[str, Any], websocket: Any = None) -> dict[str, Any]:
        async with self._lock:
            room = self._room(code)
            conn = room.connections.get(player_id)
            if conn is None:
                raise InvalidMove("Jugador inexistente")
            if websocket is not None and (not conn.connected or conn.websocket is not websocket):
                raise InvalidMove("Conexión no autorizada")
            if not isinstance(action_id, str) or not action_id or len(action_id) > 128:
                raise InvalidMove("action_id inválido")
            if not isinstance(action, str) or not action or len(action) > 32:
                raise InvalidMove("Acción inválida")
            if not isinstance(payload, dict):
                raise InvalidMove("Payload inválido")
            fingerprint = (action, json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            if action_id in conn.seen_actions:
                previous_fingerprint, _ = conn.seen_actions[action_id]
                if previous_fingerprint != fingerprint:
                    raise InvalidMove("action_id ya utilizado para otra acción")
                # Replays are idempotent, but the returned view must be fresh so
                # a delayed duplicate cannot roll a client back to an old state.
                return {"type": "state", "state": self.view_for(room, player_id)}
            if room.game is None or not room.started:
                raise InvalidMove("La partida no ha comenzado")
            game = room.game
            if action == "draw":
                game.draw(player_id)
            elif action == "take_discard":
                game.take_last_discard(player_id, payload.get("card_ids", []))
            elif action == "lower_group":
                game.lower_group(player_id, payload.get("card_ids", []))
            elif action == "discard":
                game.discard(player_id, payload["card_id"])
            else:
                raise InvalidMove("Acción desconocida")
            await self._run_bots_locked(room)
            response = {"type": "state", "state": self.view_for(room, player_id)}
            conn.seen_actions[action_id] = (fingerprint, response)
            return response

    async def chat_message(self, code: str, player_id: str, text: str) -> dict[str, Any]:
        async with self._lock:
            room = self._room(code)
            if player_id not in room.connections:
                raise InvalidMove("Jugador inexistente")
            text = str(text or "").strip()
            if not text:
                raise InvalidMove("Mensaje vacío")
            if len(text) > 300:
                raise InvalidMove("Mensaje demasiado largo")
            player = next(p for p in room.players if p.id == player_id)
            message = {"player_id": player_id, "name": player.name, "text": text}
            room.chat.append(message)
            room.chat = room.chat[-100:]
            return message

    async def request_revenge(self, code: str, player_id: str) -> None:
        async with self._lock:
            room = self._room(code)
            if room.game is None or room.game.state != GameState.WON:
                raise InvalidMove("La revancha solo está disponible al terminar la partida")
            if player_id not in room.game.active_player_ids:
                raise InvalidMove("Jugador no disponible para la revancha")
            room.revenge_votes.add(player_id)
            active = set(room.game.active_player_ids)
            if active and active.issubset(room.revenge_votes) and len(active) >= 2:
                # Start a completely fresh game with the same active players.
                active_players = [p for p in room.players if p.id in active]
                room.players = active_players
                room.connections = {pid: room.connections[pid] for pid in active if pid in room.connections}
                room.bot_controllers = {pid: c for pid, c in room.bot_controllers.items() if pid in active}
                room.game = Game(active_players, seed=secrets.randbits(64))
                room.game.start()
                room.revenge_votes.clear()
                await self._run_bots_locked(room)

    async def _run_bots_locked(self, room: Room, max_turns: int = 1000) -> int:
        """Advance bot turns only; Game remains the sole rules authority."""
        if room.game is None:
            return 0
        turns = 0
        while (
            turns < max_turns
            and room.game.state == GameState.PLAYING
            and room.game.current_player.id in room.bot_controllers
        ):
            pid = room.game.current_player.id
            room.bot_controllers[pid].play_turn(room.game, pid)
            turns += 1
        return turns

    async def run_bots(self, code: str) -> int:
        async with self._lock:
            room = self._room(code)
            turns = await self._run_bots_locked(room)
            await self.broadcast_state(room)
            return turns

    async def broadcast_state(self, room: Room) -> None:
        for pid, conn in room.connections.items():
            if conn.connected and conn.websocket is not None:
                await conn.websocket.send_json({"type": "state", "state": self.view_for(room, pid)})

    def view_for(self, room: Room, viewer_id: str) -> dict[str, Any]:
        if room.game is None:
            return {
                "room_code": room.code,
                "phase": "waiting",
                "players": [self._public_player(p, None) for p in room.players],
                "host_id": room.host_id,
            }
        game = room.game
        self._update_stats_if_finished(room)
        return {
            "room_code": room.code,
            "game_state": game.state.value,
            "phase": game.phase.value if game.phase else None,
            "turn_number": game.turn_number,
            "current_player_id": game.current_player.id if game.state == GameState.PLAYING else None,
            "deck_count": len(game.deck),
            "last_discard": self._card(game.last_discard),
            "players": [self._public_player(p, viewer_id) for p in room.players],
            "winner": None if game.winner is None else {"player_id": game.winner.player_id, "reason": game.winner.reason},
            "stats": {pid: self.player_stats.get(pid, {"wins": 0, "losses": 0}) for pid in room.connections},
            "chat": list(room.chat),
            "revenge_votes": list(room.revenge_votes),
        }

    def _update_stats_if_finished(self, room: Room) -> None:
        game = room.game
        if game is None or game.state != GameState.WON or game.winner is None:
            return
        winner_id = game.winner.player_id
        key = f"{id(game)}"
        # Track per-game accounting on the room object without exposing it.
        if getattr(room, "_stats_game_key", None) == key:
            return
        room._stats_game_key = key
        active = set(game.active_player_ids)
        for pid in active:
            self.player_stats.setdefault(pid, {"wins": 0, "losses": 0})
            if pid == winner_id:
                self.player_stats[pid]["wins"] += 1
            else:
                self.player_stats[pid]["losses"] += 1

    def _public_player(self, p: Player, viewer_id: Optional[str]) -> dict[str, Any]:
        item = {
            "id": p.id,
            "name": p.name,
            "active": p.id in (set(self._room_for_player(p.id).game.active_player_ids) if self._room_for_player(p.id).game else {x.id for x in self._room_for_player(p.id).players}),
            "connected": self._room_for_player(p.id).connections[p.id].connected,
            "card_count": len(p.hand),
            "lowered_group": None if p.lowered_group is None else {
                "id": p.lowered_group.id,
                "cards": [self._card(c) for c in p.lowered_group.cards],
            },
        }
        if p.id == viewer_id:
            item["hand"] = [self._card(c) for c in p.hand]
            item["plug"] = None if p.plug is None else {"card": self._card(p.plug.card), "target_group_id": p.plug.target_group_id}
        else:
            item["hand"] = None
            item["plug"] = None
        return item

    def _room_for_player(self, player_id: str) -> Room:
        for room in self.rooms.values():
            if player_id in room.connections:
                return room
        raise KeyError(player_id)

    @staticmethod
    def _card(card: Any) -> Optional[dict[str, Any]]:
        if card is None:
            return None
        return {"id": card.id, "rank": card.rank.name, "value": card.value, "suit": card.suit.name, "symbol": card.suit.symbol}

    def _room(self, code: str) -> Room:
        room = self.rooms.get(code.upper())
        if room is None:
            raise InvalidMove("Sala inexistente")
        return room


try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:  # pragma: no cover
    FastAPI = None


def create_app(manager: Optional[RoomManager] = None):
    if FastAPI is None:
        raise RuntimeError("Instala fastapi y uvicorn para ejecutar el servidor online")
    app = FastAPI(title="Golpeado Online", version="0.1.0")
    manager = manager or RoomManager()

    from pathlib import Path
    web_dir = Path(__file__).resolve().parent.parent / "web"
    if web_dir.exists():
        app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")

    @app.get("/")
    async def index():
        from fastapi.responses import FileResponse
        index_file = web_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"service": "golpeado-online", "ok": True})

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/rooms")
    async def create_room(body: dict[str, Any]):
        return await manager.create_room(body.get("name", "Jugador"))

    @app.post("/rooms/{code}/join")
    async def join_room(code: str, body: dict[str, Any]):
        return await manager.join_room(code, body.get("name", "Jugador"))

    @app.post("/rooms/{code}/start")
    async def start_room(code: str, body: dict[str, Any]):
        await manager.start_room(
            code, body["player_id"], None,
            body.get("bot_count", 0), body.get("bot_difficulty", "normal"),
        )
        return {"ok": True}

    @app.websocket("/ws/{code}")
    async def websocket_endpoint(websocket: WebSocket, code: str):
        await websocket.accept()
        player_id = None
        try:
            hello = json.loads(await websocket.receive_text())
            if hello.get("type") != "hello":
                raise InvalidMove("El primer mensaje debe ser hello")
            player_id = hello["player_id"]
            state = await manager.attach(code, player_id, hello["reconnect_token"], websocket)
            await websocket.send_json({"type": "state", "state": state})
            while True:
                try:
                    message = json.loads(await websocket.receive_text())
                    typ = message.get("type")
                    if typ == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue
                    if typ == "action":
                        result = await manager.action(code, player_id, message["action_id"], message["action"], message.get("payload", {}), websocket=websocket)
                        room = manager._room(code)
                        await manager.broadcast_state(room)
                        await websocket.send_json({"type": "action_ack", "action_id": message["action_id"], "state": result["state"]})
                        continue
                    if typ == "chat":
                        await manager.chat_message(code, player_id, message.get("text", ""))
                        await manager.broadcast_state(manager._room(code))
                        continue
                    if typ == "revenge":
                        await manager.request_revenge(code, player_id)
                        await manager.broadcast_state(manager._room(code))
                        continue
                    if typ == "abandon":
                        await manager.abandon(code, player_id)
                        room = manager._room(code)
                        await manager.broadcast_state(room)
                        break
                    raise InvalidMove("Mensaje desconocido")
                except WebSocketDisconnect:
                    raise
                except (InvalidMove, GameOver, KeyError) as exc:
                    await websocket.send_json({"type": "error", "code": type(exc).__name__, "message": str(exc), "action_id": message.get("action_id") if isinstance(message, dict) else None})
        except WebSocketDisconnect:
            if player_id:
                await manager.disconnect(code, player_id, websocket=websocket)
        except (InvalidMove, GameOver, KeyError) as exc:
            await websocket.send_json({"type": "error", "code": type(exc).__name__, "message": str(exc)})
        finally:
            if player_id:
                await manager.disconnect(code, player_id, websocket=websocket)

    app.state.room_manager = manager
    return app

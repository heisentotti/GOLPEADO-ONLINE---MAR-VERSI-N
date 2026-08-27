# Golpeado Online — protocolo v1

## Transporte
- HTTP/JSON para crear, entrar e iniciar salas.
- WebSocket para estado y acciones en tiempo real.

## HTTP
- `POST /rooms` body `{ "name": "..." }`
- `POST /rooms/{code}/join` body `{ "name": "..." }`
- `POST /rooms/{code}/start` body `{ "player_id": "...", "seed": optional }`
- `GET /health`

Crear/entrar devuelve `room_code`, `player_id`, `reconnect_token` y `host`.
El token es una credencial opaca de reconexión; el cliente debe guardarlo de forma privada.

## WebSocket
Conectar a `/ws/{code}` y enviar primero:

```json
{"type":"hello","player_id":"...","reconnect_token":"..."}
```

Servidor responde `state` con una vista filtrada para ese jugador.

### Acciones
```json
{"type":"action","action_id":"uuid-o-id-unico","action":"draw","payload":{}}
{"type":"action","action_id":"...","action":"take_discard","payload":{"card_ids":["..."]}}
{"type":"action","action_id":"...","action":"lower_group","payload":{"card_ids":["..."]}}
{"type":"action","action_id":"...","action":"discard","payload":{"card_id":"..."}}
```

`action_id` debe ser único por acción lógica. Repetir el mismo `action_id` no vuelve a ejecutar la acción: el servidor devuelve el resultado almacenado.

Abandono:
```json
{"type":"abandon"}
```

Latido:
```json
{"type":"ping"}
```
Servidor responde `pong`.

## Eventos del servidor
`state` contiene exclusivamente información que el jugador puede conocer:
- su propia mano;
- su propio enchufe;
- conteos de cartas de rivales;
- grupos bajados públicos;
- último descarte;
- cantidad de cartas restantes del mazo;
- turno, fase, estado y ganador.

Las manos rivales y enchufes rivales nunca se serializan. El servidor nunca envía el contenido futuro del mazo.

## Autoridad
El cliente solo solicita acciones. El servidor ejecuta la instancia única de `Game`, valida turno/fase/propiedad de cartas/reglas y luego emite nuevas vistas filtradas.

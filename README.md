# Golpeado Online

Motor de reglas + bots + interfaz de escritorio + servidor autoritativo para multijugador online.

## Multijugador online

El servidor usa FastAPI + WebSockets. El motor `Game` sigue siendo la única fuente de verdad.

### Arrancar servidor

```bash
cd /mnt/data/golpeado-online-online
python -m uvicorn golpeado.server:app --host 0.0.0.0 --port 8000
```

### Flujo

1. `POST /rooms` crea una sala y devuelve código, jugador y token de reconexión.
2. Otros jugadores usan `POST /rooms/{code}/join`.
3. El anfitrión usa `POST /rooms/{code}/start` cuando hay 2-4 jugadores.
4. Cada cliente conecta `ws://HOST:8000/ws/{code}`.
5. Primer mensaje: `hello` con `player_id` y `reconnect_token`.
6. El servidor envía una vista privada filtrada.
7. Las acciones se envían como `action` con `action_id` único.
8. Tras cada acción válida el servidor emite el nuevo estado a cada jugador.

Detalles completos en `docs/protocol.md`.

## Privacidad

El servidor jamás envía a un cliente:
- cartas ocultas de otros jugadores;
- enchufes de otros jugadores;
- cartas futuras del mazo.

El enchufe propio solo aparece en la vista de su propietario.

## Desconexión y reconexión

Una desconexión temporal no elimina al jugador. El servidor conserva la partida, mano, grupo y enchufe. El mismo `player_id + reconnect_token` puede reconectarse mientras no haya abandonado.

## Abandono

`{"type":"abandon"}` elimina definitivamente al jugador activo. Sus cartas y grupo se mueven a `out_of_play`, no al descarte ni al mazo. Si era su turno, el siguiente jugador activo recibe el turno. Si quedan menos de 2 jugadores activos, la partida termina sin ganador.

## Idempotencia

Cada acción debe tener `action_id`. Si un mensaje llega duplicado con el mismo `action_id`, el servidor no vuelve a ejecutar la acción.

## Pruebas

```bash
pytest -q
```

La suite online cubre salas de 2/3/4, privacidad, WebSocket, acciones fuera de turno, mensajes duplicados, desconexión, reconexión y abandono.

La GUI existente requiere un display gráfico para sus pruebas Tkinter; las pruebas del motor, bots, solo y servidor son independientes de la pantalla.


## Funciones online v9

- Nombre de usuario al entrar a una sala.
- Marcador de victorias y derrotas por sesión del servidor.
- Chat privado por sala.
- Revancha con aceptación de todos los jugadores activos.
- La revancha crea una partida nueva con baraja/reparto nuevos.


## Producción

La configuración gratuita de Render está en `render.yaml`. Ver `DEPLOYMENT.md` para el procedimiento.

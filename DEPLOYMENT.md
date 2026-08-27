# Golpeado Online — despliegue gratuito

## Arquitectura

Un único **Render Web Service** sirve:

- `/` → cliente web
- `/health` → health check
- `/rooms` → API HTTP
- `/ws/{room_code}` → WebSocket

No hace falta separar frontend y backend para esta primera versión.

## Coste inicial

Render mantiene Web Services gratuitos. El servicio Free se duerme después de 15 minutos sin tráfico entrante y tarda aproximadamente un minuto en volver a arrancar. Las conexiones WebSocket son compatibles. El juego envía un `ping` cada 30 segundos mientras la pestaña está abierta.

Las salas, partidas y estadísticas viven **en memoria**. Si Render reinicia, hace redeploy o el servicio se duerme, esas partidas se pierden. Esto es aceptable para el prototipo gratuito.

## GitHub

1. Crea un repositorio vacío llamado `golpeado-online`.
2. Descomprime esta versión.
3. Copia el contenido de `golpeado-online-online/` al repositorio.
4. Haz commit y push a la rama principal.

## Render

En Render:

1. `New` → `Web Service`.
2. Conecta GitHub.
3. Selecciona `golpeado-online`.
4. Render detectará `render.yaml`, o configura:
   - Runtime: Python
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn golpeado.server:app --host 0.0.0.0 --port $PORT`
   - Health Check: `/health`
   - Instance: Free
5. Deploy.

La URL será similar a:

`https://golpeado-online.onrender.com`

El navegador usará automáticamente `wss://` para WebSocket cuando esté bajo HTTPS.

## Prueba posterior al deploy

Abrir la URL en dos navegadores/dispositivos:

1. Jugador A crea sala.
2. Copiar código.
3. Jugador B entra.
4. A inicia.
5. Probar robo, descarte, grupos y enchufes.
6. Probar chat.
7. Finalizar partida.
8. Probar revancha.
9. Desconectar una pestaña y reconectar.
10. Revisar `/health`.

## Seguridad actual

El servidor es autoritativo: el cliente no controla mazo, manos, turno, grupos ni victoria.

El `reconnect_token` se entrega al jugador y no debe compartirse.

## Próxima etapa si el juego crece

Para conservar partidas y estadísticas entre reinicios habría que añadir una base de datos persistente. No se añade todavía para mantener el objetivo de $0.

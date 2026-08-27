# Golpeado Online — despliegue en Render

## Servicio

- Runtime: Python
- Build: `pip install -r requirements.txt`
- Start: `uvicorn golpeado.server:app --host 0.0.0.0 --port $PORT`
- Health: `/health`
- Cliente web: `/`
- WebSocket: `/ws/{room_code}`

## Render

El repositorio debe estar en GitHub/GitLab/Bitbucket. En Render se puede crear un Web Service desde el repositorio o usar el `render.yaml` de este proyecto.

En producción el navegador usa `https://...onrender.com` y WebSocket seguro `wss://...onrender.com/ws/CODIGO` automáticamente.

## Importante

Las salas viven en memoria. Un reinicio o spin-down del servicio elimina las partidas activas. Esto es aceptable para la primera versión gratuita/hobby, pero no debe interpretarse como persistencia de partidas.

El cliente web y el servidor están en el mismo servicio para evitar una configuración CORS adicional.

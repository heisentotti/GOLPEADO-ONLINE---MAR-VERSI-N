# Golpeado Online — QA / Security Report

Fecha: 2026-08-26

## Alcance

QA funcional, bots, multijugador, privacidad y seguridad del motor actual. No se agregaron funcionalidades de juego.

## Resultado global

- 104 pruebas automatizadas: PASS
- Auditoría adicional de reglas: 11 casos explícitos PASS
- Auditoría exhaustiva: 100 grupos legales de 3 cartas, 0 discrepancias en sus cartas de enchufe
- 0 fallos al ejecutar la suite completa bajo Xvfb
- 3,000 partidas de bots adicionales: 1,000 de 2 jugadores, 1,000 de 3 jugadores y 1,000 de 4 jugadores
- 3,000/3,000 partidas completadas
- 0 jugadas ilegales generadas por bots
- 0 estados imposibles detectados
- 0 fallos de invariantes
- 0 partidas estancadas con límite de 2,000 turnos

## Hallazgos corregidos

### QA-001 — Bajar grupo antes de obtener la carta del turno
Se detectó que `Game.lower_group()` aceptaba la fase `DRAW`, permitiendo saltarse la obtención obligatoria de la carta. Se corrigió para aceptar la bajada únicamente después de obtener la carta, en fase `ACTION`.

### SEC-001 — Semilla del mazo controlable mediante HTTP
La ruta HTTP de inicio aceptaba una semilla enviada por el cliente. Eso permitía a un cliente malicioso elegir un mazo determinista y potencialmente reconstruir información privada. La ruta HTTP ahora nunca pasa una semilla proporcionada por el cliente; el servidor genera una semilla criptográficamente aleatoria cuando el inicio no proviene de una capa de prueba confiable.

### SEC-002 — Socket antiguo válido después de reconexión
Una reconexión reemplazaba el socket registrado, pero el socket antiguo podía intentar enviar acciones porque `action()` no verificaba la identidad del socket. Se corrigió: el socket debe ser exactamente el socket actualmente autenticado para esa sesión.

### SEC-003 — Cierre de socket antiguo podía desconectar la sesión nueva
El `finally` de un socket viejo podía marcar desconectada la conexión nueva después de una reconexión. `disconnect()` ahora comprueba la identidad del socket antes de modificar la sesión.

### QA-002 — Replay de action_id podía devolver un estado obsoleto
Las acciones duplicadas devolvían una respuesta almacenada con un snapshot antiguo. Se mantiene la idempotencia, pero los replays ahora reciben una vista actualizada. Además, reutilizar un `action_id` para una acción/payload diferente se rechaza.

### QA-003 — Métrica de invariant failures
La simulación ya distinguía explícitamente una violación de invariantes de otros estados imposibles, mejorando el diagnóstico de QA.

## Privacidad verificada

Para cada jugador:

- su propia mano: visible
- su propio enchufe: visible
- grupos bajados: públicos
- último descarte: público
- manos de rivales: ocultas
- enchufes de rivales: ocultos
- contenido futuro del mazo: oculto

Los bots reciben una `BotObservation` restringida y no reciben manos rivales, enchufes rivales ni el mazo no repartido.

## Pruebas de seguridad

Se verificaron:

- acciones fuera de turno
- payloads con campos falsos de mano/turno/victoria
- acciones duplicadas
- reutilización de `action_id`
- socket antiguo después de reconexión
- reconexión con credenciales inválidas
- intento de reconectar tras abandono
- capacidad máxima de sala
- inicio por usuario no anfitrión
- grupos inválidos
- descarte de cartas no poseídas
- manipulación unilateral de estado del cliente

## Simulación

### 2 jugadores
- 1,000 partidas
- 1,000 completadas
- promedio: 53.325 turnos
- máximo: 319
- ilegales: 0
- imposibles: 0
- invariantes: 0
- estancadas: 0

### 3 jugadores
- 1,000 partidas
- 1,000 completadas
- promedio: 49.005 turnos
- máximo: 1,690
- ilegales: 0
- imposibles: 0
- invariantes: 0
- estancadas: 0

### 4 jugadores
- 1,000 partidas
- 1,000 completadas
- promedio: 54.277 turnos
- máximo: 393
- ilegales: 0
- imposibles: 0
- invariantes: 0
- estancadas: 0

## Balance observado

No se detectaron estados inválidos ni partidas infinitas. Sí existe una diferencia apreciable entre estrategias de bot en algunas configuraciones; esto se considera un asunto de balance/IA, no un error de reglas. No se modificó porque la tarea solicitó QA y corrección de errores, no rediseño de estrategias.

## Riesgos pendientes

1. El servidor sigue siendo una implementación de referencia/inicial y todavía requiere hardening antes de producción: TLS/HTTPS, gestión de secretos de despliegue, límites/rate limiting y observabilidad.
2. La persistencia de salas/partidas todavía es en memoria; un reinicio del proceso elimina las partidas activas.
3. No se realizó una prueba de carga distribuida real con múltiples procesos/nodos.
4. Los tokens de reconexión deben protegerse como credenciales de sesión y transmitirse únicamente mediante canal seguro en producción.
5. El balance de dificultades de bots requiere una fase específica de tuning si se busca igualdad competitiva.



### QA-004 — Enchufe en los extremos con As
La auditoría exhaustiva detectó que `completing_cards_for_group()` no contemplaba ambos extremos cuando el As puede actuar como 1 o 14. Por ejemplo, `2-3-4` debe aceptar `A` y `5`, y `J-Q-K` debe aceptar `10` y `A`. Se corrigió derivando los candidatos directamente del mismo validador autoritativo `is_valid_group()`.

## Conclusión

El sistema pasó la batería funcional y de seguridad ejecutada. Los fallos encontrados durante esta ronda fueron corregidos y la suite completa quedó en PASS. No se realizó despliegue a producción.

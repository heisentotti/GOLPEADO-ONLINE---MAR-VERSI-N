# UI POLISH V17

Cambios realizados:
- Rediseño de cartas de la mano con proporción y composición visual de baraja convencional.
- Rangos normalizados: A, 2-10, J, Q, K.
- Palos visibles con símbolos ♣ ♦ ♥ ♠ y color rojo para corazones/diamantes.
- Cartas numéricas con distribución visual de pips.
- J/Q/K con tratamiento visual de carta de figura.
- Estado seleccionado con elevación y borde dorado.
- Nuevo indicador central de turno: "Turno de <jugador>".
- El jugador cuyo turno está activo recibe borde rojo y resplandor en la lista de jugadores.
- Etiqueta "SU TURNO" para el jugador activo.
- El jugador local ve "¡ES TU TURNO!" cuando corresponde.
- El descarte usa el mismo lenguaje visual de carta y no se puede seleccionar como carta de la mano.
- Se mantiene el orden automático existente.
- No se modificaron las reglas del motor ni el protocolo online.

Validación:
- JavaScript de web/index.html validado con Node --check.
- Suite no gráfica: 100% OK (los tests de motor, bots, online, reglas, solo y social pasan).
- El test de GUI no se ejecutó en entorno sin display; su fallo en este entorno es por Tkinter/TclError al no existir pantalla gráfica, no por el cambio web.

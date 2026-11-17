# Experimento de latencia entre g3a y g3b

## Pregunta

¿Cuánto tarda un mensaje enviado desde `g3a` en aparecer en el historial de `g3b`?

## Hipótesis

La latencia promedio de cada repetición será menor de 1500 ms. Cuando la cola de envío está vacía, el servidor la consulta una vez por segundo.

## Método

Se ejecutaron `g3a`, `g3b` y el central simulado en Docker en la misma computadora. Se envió un mensaje de calentamiento y luego se realizaron tres repeticiones de diez mensajes consecutivos.

Para cada mensaje, el script inició el cronómetro antes de enviarlo a `g3a` y lo detuvo cuando el mismo identificador apareció en el historial de `g3b`. El historial se consultó cada 50 ms, por lo que el tiempo medido incluye la espera hasta la siguiente consulta.

## Resultados

| Repetición | Mensajes | Promedio (ms) | Mínimo (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| 1 | 10 | 1020,90 | 995,06 | 1051,07 |
| 2 | 10 | 1016,24 | 979,27 | 1067,38 |
| 3 | 10 | 1020,94 | 1016,18 | 1028,67 |

## Conclusión

Los tres promedios quedaron por debajo de 1500 ms, lo que respalda la hipótesis en el entorno local de prueba. El promedio general fue de aproximadamente 1019,36 ms y los tiempos observados estuvieron entre 979,27 y 1067,38 ms.

Los datos individuales están en `resultados-latencia.csv` y el script de medición está en `medir_latencia.py`.
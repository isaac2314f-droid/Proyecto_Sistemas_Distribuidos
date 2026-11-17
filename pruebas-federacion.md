# Pruebas de federación

| Prueba | Resultado observado |
|---|---|
| Envío de g3a a g3b | En el puerto 8001 apareció `isaac@g3a: Hola desde g3a`. |
| Envío de g3b a g3a | En el puerto 8000 apareció `luis@g3b: Verificación desde el puerto 8001`. |
| Recuperación tras una caída | Se detuvo g3b, se envió un mensaje desde g3a y, al volver a iniciar g3b, el mensaje recuperado apareció una sola vez. |
# Unity Realtime Client

Este ejemplo muestra cómo conectarse al servidor de FastAPI ubicado en `server.py` desde un proyecto de Unity utilizando WebSockets.

## Uso

1. Asegúrate de que el servidor esté en ejecución:
   ```bash
   cd examples/realtime/unity
   uv run python server.py
   ```
2. Copia `RealtimeUnityClient.cs` en tu proyecto de Unity y asígnalo a un `GameObject`.
3. Ejecuta la escena. El cliente se conectará automáticamente y registrará los mensajes recibidos.
4. Llama a `SendText("hola")` o `SendAudio(muestras)` para enviar datos al servidor.

El script utiliza `System.Net.WebSockets` disponible en las versiones modernas de Unity.

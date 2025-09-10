# Unity Client Setup

Este documento describe cómo usar el script `UnityRealtimeClient.cs` para conectar un proyecto de Unity con el servidor de ejemplo.

## Pasos

1. Copia `UnityRealtimeClient.cs` en tu proyecto de Unity y adjúntalo a un `GameObject` en la escena.
2. Modifica los campos `Session Id` y `Server Url` en el inspector si es necesario.
3. Desde otro script, llama a `await Connect()` para abrir la conexión y a `await Disconnect()` para cerrarla.
4. Usa `SendAudio(samples)` para mandar audio PCM de 16 bits.
5. Suscríbete a los eventos `OnTranscription` y `OnAudio` para recibir transcripciones y audio de respuesta.

El script utiliza `System.Net.WebSockets`, por lo que se recomienda usar el runtime .NET 4.x.

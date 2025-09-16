using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

#if TMP_PRESENT
using TMPro;
#endif

public class RealtimeNPCClient : MonoBehaviour
{
    [Header("Servidor")]
    [Tooltip("Base WebSocket, p.ej. ws://localhost:8000/ws")]
    public string serverUrl = "ws://localhost:8000/ws";

    [Header("Captura (open-mic)")]
    public int captureSampleRate = 24000;
    public bool echoCancellation = true;   // (solo informativo; Unity Microphone no aplica EC)
    public bool noiseSuppression = true;   // (solo informativo)

    [Header("Salida de audio")]
    public int outputSampleRate = 24000;
    [Tooltip("Fade por chunk (seg) para evitar clics")]
    public float playbackFadeSec = 0.02f;

    [Header("UI (opcional)")]
#if TMP_PRESENT
    public TextMeshProUGUI transcriptTMP;
#endif
    public UnityEngine.UI.Text transcriptText;

    // --- Internos ---
    private string sessionId;
    private ClientWebSocket wsMain;     // /ws/{session_id}
    private ClientWebSocket wsEvents;   // /ws/{session_id}/events (opcional)
    private CancellationTokenSource cts;

    // Open-mic
    private AudioClip micClip;
    private string micDevice;
    private int micReadPos;
    private bool isMuted = false;
    private bool isCapturing = false;

    // UI transcripts
    private readonly ConcurrentQueue<string> transcriptQueue = new ConcurrentQueue<string>();
    private string latestTranscript = "";

    // Playback
    private AudioSource audioSource;
    private readonly ConcurrentQueue<short[]> pcmQueue = new ConcurrentQueue<short[]>();
    private float[] playbackResidual; // para aplicar fade
    private int playbackResidualPos;

    // Imagen (chunking)
    private const int IMAGE_CHUNK = 60_000;

    // ===== Ciclo de vida =====

    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.playOnAwake = true;
        audioSource.loop = true;
        audioSource.clip = AudioClip.Create("NPC_Output", outputSampleRate * 10, 1, outputSampleRate, true, OnAudioRead, OnAudioSetPos);
        audioSource.Play();
    }

    private async void Start()
    {
        await ConnectAndStartOpenMic();
    }

    private async void OnDestroy()
    {
        await Shutdown();
    }

    // ===== Conexión =====

    public async Task ConnectAndStartOpenMic()
    {
        sessionId = "session_" + Guid.NewGuid().ToString("N").Substring(0, 9);
        cts = new CancellationTokenSource();

        // MAIN
        wsMain = new ClientWebSocket();
        var mainUri = new Uri($"{serverUrl}/{sessionId}");
        await wsMain.ConnectAsync(mainUri, cts.Token);
        Debug.Log($"[RealtimeNPC] Conectado MAIN: {mainUri}");
        _ = ReceiveLoop(wsMain, "main");

        // EVENTS (opcional). Si falla, seguimos con MAIN únicamente.
        try
        {
            wsEvents = new ClientWebSocket();
            var evUri = new Uri($"{serverUrl}/{sessionId}/events");
            await wsEvents.ConnectAsync(evUri, cts.Token);
            Debug.Log($"[RealtimeNPC] Conectado EVENTS: {evUri}");
            _ = ReceiveLoop(wsEvents, "events");
        }
        catch (Exception ex)
        {
            Debug.Log($"[RealtimeNPC] Events no disponible (ok): {ex.Message}");
            wsEvents?.Dispose();
            wsEvents = null;
        }

        StartOpenMic();
    }

    private async Task Shutdown()
    {
        try
        {
            StopOpenMic();
            if (wsMain != null)
            {
                if (wsMain.State == WebSocketState.Open)
                    await wsMain.CloseAsync(WebSocketCloseStatus.NormalClosure, "closing", cts.Token);
                wsMain.Dispose();
            }
            if (wsEvents != null)
            {
                if (wsEvents.State == WebSocketState.Open)
                    await wsEvents.CloseAsync(WebSocketCloseStatus.NormalClosure, "closing", cts.Token);
                wsEvents.Dispose();
            }
        }
        catch (Exception e) { Debug.LogWarning(e); }
        finally { cts?.Dispose(); }
    }

    private async Task ReceiveLoop(ClientWebSocket socket, string tag)
    {
        var buffer = new byte[64 * 1024];
        try
        {
            while (socket.State == WebSocketState.Open)
            {
                var sb = new StringBuilder();
                WebSocketReceiveResult res;
                do
                {
                    res = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                    if (res.MessageType == WebSocketMessageType.Close)
                    {
                        await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "", cts.Token);
                        Debug.Log($"[RealtimeNPC] {tag} cerrado por servidor.");
                        return;
                    }
                    if (res.MessageType == WebSocketMessageType.Text)
                        sb.Append(Encoding.UTF8.GetString(buffer, 0, res.Count));
                } while (!res.EndOfMessage);

                HandleInbound(sb.ToString(), tag);
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex) { Debug.LogWarning($"[RealtimeNPC] ReceiveLoop {tag} error: {ex}"); }
    }

    // ===== Open-mic =====

    public void ToggleMute(bool value)
    {
        isMuted = value;
    }

    public void StartOpenMic()
    {
        if (isCapturing) return;

#if UNITY_WEBGL && !UNITY_EDITOR
        Debug.LogWarning("Microphone no soportado en WebGL sin permisos/navegador. Prueba en escritorio.");
#endif
        if (Microphone.devices.Length == 0)
        {
            Debug.LogWarning("No hay micrófono.");
            return;
        }
        micDevice = Microphone.devices[0];
        micClip = Microphone.Start(micDevice, true, 10, captureSampleRate);
        micReadPos = 0;
        isCapturing = true;
        StartCoroutine(CaptureLoop());
        Debug.Log($"[RealtimeNPC] Open-mic iniciado @ {captureSampleRate} Hz, device={micDevice}");
    }

    public void StopOpenMic()
    {
        if (!isCapturing) return;
        isCapturing = false;
        if (Microphone.IsRecording(micDevice)) Microphone.End(micDevice);
        micClip = null;
    }

    private System.Collections.IEnumerator CaptureLoop()
    {
        var wait = new WaitForSeconds(0.03f); // ~33 ms
        float[] buffer = new float[4096];

        while (isCapturing)
        {
            yield return wait;
            if (micClip == null || wsMain == null || wsMain.State != WebSocketState.Open) continue;

            int micPos = Microphone.GetPosition(micDevice);
            int available = micPos - micReadPos;
            if (available < 0) available += micClip.samples;

            // Procesar en lotes razonables
            int toRead = Mathf.Min(available, buffer.Length);
            while (toRead > 0)
            {
                micClip.GetData(buffer, micReadPos);
                micReadPos = (micReadPos + toRead) % micClip.samples;

                if (!isMuted)
                {
                    // float32 -> int16
                    short[] pcm16 = new short[toRead];
                    for (int i = 0; i < toRead; i++)
                    {
                        float v = Mathf.Clamp(buffer[i], -1f, 1f);
                        pcm16[i] = (short)Mathf.RoundToInt(v * 32767f);
                    }
                    SendAudio(pcm16);
                }

                // volver a calcular
                micPos = Microphone.GetPosition(micDevice);
                available = micPos - micReadPos;
                if (available < 0) available += micClip.samples;
                toRead = Mathf.Min(available, buffer.Length);
            }
        }
    }

    // ===== ENVÍO =====

    public async void SendText(string text)
    {
        if (wsMain == null || wsMain.State != WebSocketState.Open) return;
        // Interrumpe reproducción/LLM en curso como en tu JS
        await SendRaw(wsMain, "{\"type\":\"interrupt\"}");
        string payload = $"{{\"type\":\"text\",\"text\":\"{Escape(text)}\"}}";
        await SendRaw(wsMain, payload);
    }

    public async void SendAudio(short[] samples)
    {
        if (wsMain == null || wsMain.State != WebSocketState.Open) return;
        // {"type":"audio","data":[int16,...]}
        var sb = new StringBuilder();
        sb.Append("{\"type\":\"audio\",\"data\":[");
        for (int i = 0; i < samples.Length; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append(samples[i]);
        }
        sb.Append("]}");
        await SendRaw(wsMain, sb.ToString());
    }

    /// <summary>Forzar commit del turno actual (override del VAD server).</summary>
    public async void CommitAudio()
    {
        if (wsMain == null || wsMain.State != WebSocketState.Open) return;
        await SendRaw(wsMain, "{\"type\":\"commit_audio\"}");
    }

    /// <summary>Envía una imagen (Texture2D) como Data URL en chunks. Opcional: prompt de texto.</summary>
    public async void SendImage(Texture2D tex, string promptText = "")
    {
        if (wsMain == null || wsMain.State != WebSocketState.Open || tex == null) return;

        await SendRaw(wsMain, "{\"type\":\"interrupt\"}");

        // Comprimir a JPG (0.85 aprox)
        byte[] jpg = tex.EncodeToJPG(85);
        string b64 = Convert.ToBase64String(jpg);
        string dataUrl = "data:image/jpeg;base64," + b64;

        string id = "img_" + Guid.NewGuid().ToString("N").Substring(0, 6);
        string start = $"{{\"type\":\"image_start\",\"id\":\"{id}\",\"text\":\"{Escape(promptText)}\"}}";
        await SendRaw(wsMain, start);

        // chunking
        for (int i = 0; i < dataUrl.Length; i += IMAGE_CHUNK)
        {
            string chunk = dataUrl.Substring(i, Math.Min(IMAGE_CHUNK, dataUrl.Length - i));
            string msg = $"{{\"type\":\"image_chunk\",\"id\":\"{id}\",\"chunk\":\"{Escape(chunk)}\"}}";
            await SendRaw(wsMain, msg);
        }

        string end = $"{{\"type\":\"image_end\",\"id\":\"{id}\"}}";
        await SendRaw(wsMain, end);
    }

    private static async Task SendRaw(ClientWebSocket socket, string payload)
    {
        var bytes = Encoding.UTF8.GetBytes(payload);
        await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
    }

    private static string Escape(string s)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
    }

    // ===== RECEPCIÓN / PARSING =====

    private void HandleInbound(string json, string tag)
    {
        // 1) audio base64 → cola PCM16
        if (TryExtractAudioBase64(json, out var base64))
        {
            var bytes = SafeFromBase64(base64);
            if (bytes != null && bytes.Length >= 2 && bytes.Length % 2 == 0)
            {
                short[] pcm = new short[bytes.Length / 2];
                Buffer.BlockCopy(bytes, 0, pcm, 0, bytes.Length);
                ApplyFadeInOut(pcm, playbackFadeSec, outputSampleRate);
                pcmQueue.Enqueue(pcm);
            }
        }

        // 2) transcripción / texto
        if (TryExtractText(json, out var txt) && !string.IsNullOrEmpty(txt))
        {
            transcriptQueue.Enqueue(txt);
        }

        // 3) eventos de control
        if (json.Contains("\"type\":\"audio_interrupted\""))
        {
            // vaciamos cola de salida
            ClearPlayback();
        }
        else if (json.Contains("\"type\":\"input_audio_timeout_triggered\""))
        {
            // igual que en tu JS: pide commit para agilizar respuesta
            CommitAudio();
        }

        // 4) historial (manejo simple: extraer último texto)
        if ((json.Contains("\"type\":\"history_updated\"") || json.Contains("\"type\":\"history_added\"")) &&
            TryExtractLatestHistoryText(json, out var histText))
        {
            if (!string.IsNullOrEmpty(histText))
                transcriptQueue.Enqueue(histText);
        }

#if UNITY_EDITOR
        // Debug opcional:
        // Debug.Log($"[{tag}] {json}");
#endif
    }

    private static byte[] SafeFromBase64(string s)
    {
        try { return Convert.FromBase64String(s); } catch { return null; }
    }

    // Busca "type":"audio" y campo "audio":"<base64>" (o "data":"<base64>")
    private static bool TryExtractAudioBase64(string json, out string base64)
    {
        base64 = null;
        if (!json.Contains("\"type\":\"audio\"") && !json.Contains("\"type\":\"response.audio.delta\""))
            return false;

        base64 = ExtractStringField(json, "audio");
        if (string.IsNullOrEmpty(base64))
            base64 = ExtractStringField(json, "data");

        // Heurística base64
        if (!string.IsNullOrEmpty(base64) && base64.Length > 16)
            return true;

        base64 = null;
        return false;
    }

    // Busca "text":"..."
    private static bool TryExtractText(string json, out string text)
    {
        text = null;

        // Prioriza eventos típicos:
        // response.output_text.delta / transcript / message content.*text
        int i = json.IndexOf("\"text\":\"", StringComparison.Ordinal);
        if (i < 0) return false;

        int start = i + "\"text\":\"".Length;
        var sb = new StringBuilder();
        for (int p = start; p < json.Length; p++)
        {
            char c = json[p];
            if (c == '\"')
            {
                text = sb.ToString();
                return !string.IsNullOrEmpty(text);
            }
            if (c == '\\' && p + 1 < json.Length)
            {
                char n = json[p + 1];
                if (n == 'n') { sb.Append('\n'); p++; continue; }
                if (n == 'r') { sb.Append('\r'); p++; continue; }
                if (n == 't') { sb.Append('\t'); p++; continue; }
                if (n == '\\' || n == '\"' || n == '/') { sb.Append(n); p++; continue; }
            }
            else sb.Append(c);
        }
        return false;
    }

    private static string ExtractStringField(string json, string field)
    {
        string key = $"\"{field}\":\"";
        int i = json.IndexOf(key, StringComparison.Ordinal);
        if (i < 0) return null;
        int start = i + key.Length;
        var sb = new StringBuilder();
        for (int p = start; p < json.Length; p++)
        {
            char c = json[p];
            if (c == '\"') return sb.ToString();
            if (c == '\\' && p + 1 < json.Length)
            {
                char n = json[p + 1];
                if (n == 'n') { sb.Append('\n'); p++; continue; }
                if (n == 'r') { sb.Append('\r'); p++; continue; }
                if (n == 't') { sb.Append('\t'); p++; continue; }
                if (n == '\\' || n == '\"' || n == '/') { sb.Append(n); p++; continue; }
            }
            else sb.Append(c);
        }
        return null;
    }

    // Extrae texto “último” de una estructura de history simple (heurístico)
    private static bool TryExtractLatestHistoryText(string json, out string text)
    {
        text = null;
        // Busca el último "text":"..." del mensaje
        int last = json.LastIndexOf("\"text\":\"", StringComparison.Ordinal);
        if (last < 0) return false;
        int start = last + "\"text\":\"".Length;
        var sb = new StringBuilder();
        for (int p = start; p < json.Length; p++)
        {
            char c = json[p];
            if (c == '\"') { text = sb.ToString(); return true; }
            if (c == '\\' && p + 1 < json.Length)
            {
                char n = json[p + 1];
                if (n == 'n') { sb.Append('\n'); p++; continue; }
                if (n == 'r') { sb.Append('\r'); p++; continue; }
                if (n == 't') { sb.Append('\t'); p++; continue; }
                if (n == '\\' || n == '\"' || n == '/') { sb.Append(n); p++; continue; }
            }
            else sb.Append(c);
        }
        return false;
    }

    // ===== Playback =====

    private void OnAudioRead(float[] data)
    {
        int i = 0;

        // 1) Consumir residual (si quedó de un frame anterior después del fade)
        if (playbackResidual != null)
        {
            while (i < data.Length && playbackResidualPos < playbackResidual.Length)
            {
                data[i++] = playbackResidual[playbackResidualPos++];
            }
            if (playbackResidualPos >= playbackResidual.Length)
            {
                playbackResidual = null;
                playbackResidualPos = 0;
            }
        }

        // 2) Vaciar cola de PCM16->float
        while (i < data.Length)
        {
            if (!pcmQueue.TryDequeue(out var pcm))
            {
                // silencio si no hay datos
                while (i < data.Length) data[i++] = 0f;
                return;
            }

            // Convertir short[] a float[]
            int n = pcm.Length;
            float[] chunk = new float[n];
            const float inv = 1f / 32768f;
            for (int s = 0; s < n; s++) chunk[s] = Mathf.Clamp(pcm[s] * inv, -1f, 1f);

            int copy = Mathf.Min(chunk.Length, data.Length - i);
            Array.Copy(chunk, 0, data, i, copy);
            i += copy;

            if (copy < chunk.Length)
            {
                // guardar residual
                int rest = chunk.Length - copy;
                playbackResidual = new float[rest];
                Array.Copy(chunk, copy, playbackResidual, 0, rest);
                playbackResidualPos = 0;
            }
        }
    }

    private void OnAudioSetPos(int pos) { }

    private void ClearPlayback()
    {
        while (pcmQueue.TryDequeue(out _)) { }
        playbackResidual = null;
        playbackResidualPos = 0;
    }

    private void ApplyFadeInOut(short[] pcm, float fadeSec, int sr)
    {
        if (fadeSec <= 0f) return;
        int fadeSamples = Mathf.Clamp(Mathf.RoundToInt(fadeSec * sr), 8, Mathf.Min(2000, pcm.Length / 4));
        // In
        for (int i = 0; i < fadeSamples && i < pcm.Length; i++)
        {
            float g = (i + 1) / (float)fadeSamples;
            pcm[i] = (short)Mathf.RoundToInt(pcm[i] * g);
        }
        // Out
        for (int i = 0; i < fadeSamples && i < pcm.Length; i++)
        {
            int idx = pcm.Length - 1 - i;
            float g = (i + 1) / (float)fadeSamples;
            pcm[idx] = (short)Mathf.RoundToInt(pcm[idx] * (1f - g));
        }
    }

    // ===== UI =====

    private void Update()
    {
        while (transcriptQueue.TryDequeue(out var delta))
        {
            latestTranscript += delta;
#if TMP_PRESENT
            if (transcriptTMP) transcriptTMP.text = latestTranscript;
#endif
            if (transcriptText) transcriptText.text = latestTranscript;
        }
    }
}

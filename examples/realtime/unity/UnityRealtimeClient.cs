using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

/// <summary>
/// Simple Unity client for the realtime demo server.
/// Opens a WebSocket connection to send and receive audio.
/// The server transcribes incoming audio and returns transcripts and audio responses.
/// </summary>
public class UnityRealtimeClient : MonoBehaviour
{
    [SerializeField] private string sessionId = "test";
    [SerializeField] private string serverUrl = "ws://localhost:8000";

    private ClientWebSocket socket;
    private CancellationTokenSource cancellation;

    /// <summary>
    /// Event fired when a transcript is received from the server.
    /// </summary>
    public Action<string> OnTranscription;

    /// <summary>
    /// Event fired when audio is received from the server.
    /// </summary>
    public Action<short[]> OnAudio;

    /// <summary>
    /// Connect to the realtime server.
    /// </summary>
    public async Task Connect()
    {
        if (socket != null && socket.State == WebSocketState.Open)
        {
            return;
        }

        cancellation = new CancellationTokenSource();
        socket = new ClientWebSocket();
        Uri uri = new Uri($"{serverUrl}/ws/{sessionId}");
        await socket.ConnectAsync(uri, cancellation.Token);
        _ = ReceiveLoop();
    }

    /// <summary>
    /// Disconnect from the realtime server.
    /// </summary>
    public async Task Disconnect()
    {
        if (socket != null)
        {
            await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, string.Empty, cancellation.Token);
            socket.Dispose();
            socket = null;
        }
        cancellation?.Cancel();
    }

    /// <summary>
    /// Send raw 16-bit PCM samples to the server.
    /// </summary>
    public async Task SendAudio(short[] samples)
    {
        if (socket == null || socket.State != WebSocketState.Open)
        {
            return;
        }

        var message = new AudioMessage { data = samples };
        string json = JsonUtility.ToJson(message);
        byte[] buffer = Encoding.UTF8.GetBytes(json);
        await socket.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, cancellation.Token);
    }

    private async Task ReceiveLoop()
    {
        var buffer = new byte[4096];
        while (socket != null && socket.State == WebSocketState.Open)
        {
            WebSocketReceiveResult result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellation.Token);
            if (result.MessageType == WebSocketMessageType.Close)
            {
                await Disconnect();
            }
            else
            {
                string json = Encoding.UTF8.GetString(buffer, 0, result.Count);
                var evt = JsonUtility.FromJson<RealtimeEvent>(json);
                if (evt.type == "audio" && !string.IsNullOrEmpty(evt.audio))
                {
                    byte[] audioBytes = Convert.FromBase64String(evt.audio);
                    short[] samples = new short[audioBytes.Length / 2];
                    Buffer.BlockCopy(audioBytes, 0, samples, 0, audioBytes.Length);
                    OnAudio?.Invoke(samples);
                }
                else if (evt.type == "history_updated" && evt.history != null)
                {
                    foreach (var item in evt.history)
                    {
                        if (item.content == null)
                        {
                            continue;
                        }
                        foreach (var content in item.content)
                        {
                            if (content.type == "input_text")
                            {
                                OnTranscription?.Invoke(content.text);
                            }
                        }
                    }
                }
                else
                {
                    Debug.Log($"Server: {json}");
                }
            }
        }
    }

    async void OnDestroy()
    {
        await Disconnect();
    }

    [Serializable]
    private class AudioMessage
    {
        public string type = "audio";
        public short[] data;
    }

    [Serializable]
    private class RealtimeEvent
    {
        public string type;
        public string audio;
        public HistoryItem[] history;
    }

    [Serializable]
    private class HistoryItem
    {
        public HistoryContent[] content;
    }

    [Serializable]
    private class HistoryContent
    {
        public string type;
        public string text;
    }
}

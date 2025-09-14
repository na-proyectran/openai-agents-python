using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

public class RealtimeUnityClient : MonoBehaviour
{
    [Tooltip("Base WebSocket URL, e.g. ws://localhost:8000/ws")] public string serverUrl = "ws://localhost:8000/ws";
    private ClientWebSocket socket;
    private CancellationTokenSource cts;
    private string sessionId;

    public async void Start()
    {
        await Connect();
    }

    public async Task Connect()
    {
        sessionId = Guid.NewGuid().ToString();
        socket = new ClientWebSocket();
        cts = new CancellationTokenSource();
        var uri = new Uri($"{serverUrl}/{sessionId}");
        await socket.ConnectAsync(uri, cts.Token);
        Debug.Log($"Connected to {uri}.");
        _ = ReceiveLoop();
    }

    private async Task ReceiveLoop()
    {
        var buffer = new byte[8192];
        while (socket.State == WebSocketState.Open)
        {
            var result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
            if (result.MessageType == WebSocketMessageType.Close)
            {
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, string.Empty, cts.Token);
                break;
            }
            var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
            Debug.Log($"Received: {message}");
        }
    }

    public async void SendText(string text)
    {
        if (socket == null || socket.State != WebSocketState.Open)
        {
            Debug.LogWarning("WebSocket is not connected.");
            return;
        }

        var payload = $"{{\"type\":\"text\",\"text\":\"{text}\"}}";
        var bytes = Encoding.UTF8.GetBytes(payload);
        await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token);
    }

    public async void SendAudio(short[] samples)
    {
        if (socket == null || socket.State != WebSocketState.Open)
        {
            Debug.LogWarning("WebSocket is not connected.");
            return;
        }

        string data = string.Join(",", samples);
        var payload = $"{{\"type\":\"audio\",\"data\":[{data}]}}";
        var bytes = Encoding.UTF8.GetBytes(payload);
        await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token);
    }

    private async void OnDestroy()
    {
        if (socket != null)
        {
            if (socket.State == WebSocketState.Open)
            {
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "closing", cts.Token);
            }
            socket.Dispose();
            cts.Dispose();
        }
    }
}

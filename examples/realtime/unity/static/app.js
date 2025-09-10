class RealtimeLog {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.sessionId = null;
        this.connectBtn = document.getElementById('connectBtn');
        this.status = document.getElementById('status');
        this.sessionInput = document.getElementById('sessionInput');
        this.messagesContent = document.getElementById('messagesContent');
        this.eventsContent = document.getElementById('eventsContent');
        this.toolsContent = document.getElementById('toolsContent');
        this.connectBtn.addEventListener('click', () => {
            if (this.isConnected) {
                this.disconnect();
            } else {
                this.connect();
            }
        });
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
    }

    connect() {
        this.sessionId = this.sessionInput.value.trim() || this.generateSessionId();
        this.sessionInput.value = this.sessionId;
        this.ws = new WebSocket(`ws://localhost:8000/ws/${this.sessionId}`);
        this.ws.onopen = () => {
            this.isConnected = true;
            this.updateUI();
        };
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleEvent(data);
        };
        this.ws.onclose = () => {
            this.isConnected = false;
            this.updateUI();
        };
        this.ws.onerror = (error) => console.error('WebSocket error:', error);
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }

    updateUI() {
        if (this.isConnected) {
            this.connectBtn.textContent = 'Disconnect';
            this.connectBtn.className = 'connect-btn connected';
            this.status.textContent = 'Connected';
            this.status.className = 'status connected';
        } else {
            this.connectBtn.textContent = 'Connect';
            this.connectBtn.className = 'connect-btn disconnected';
            this.status.textContent = 'Disconnected';
            this.status.className = 'status disconnected';
        }
    }

    handleEvent(event) {
        this.addRawEvent(event);
        if (event.type === 'history_updated') {
            this.updateMessages(event.history);
        }
        if (event.type === 'tool_start' || event.type === 'tool_end' || event.type === 'handoff') {
            this.addToolEvent(event);
        }
    }

    updateMessages(history) {
        this.messagesContent.innerHTML = '';
        if (history && Array.isArray(history)) {
            history.forEach((item) => {
                if (item.type === 'message') {
                    const role = item.role;
                    let content = '';
                    if (Array.isArray(item.content)) {
                        item.content.forEach((part) => {
                            if (part.type === 'text' && part.text) {
                                content += part.text;
                            } else if (part.type === 'audio' && part.transcript) {
                                content += part.transcript;
                            } else if (part.type === 'input_audio' && part.transcript) {
                                content += part.transcript;
                            } else if (part.type === 'input_text' && part.text) {
                                content += part.text;
                            }
                        });
                    }
                    if (content.trim()) {
                        this.addMessage(role, content.trim());
                    }
                }
            });
        }
    }

    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.textContent = content;
        messageDiv.appendChild(bubbleDiv);
        this.messagesContent.appendChild(messageDiv);
        this.messagesContent.scrollTop = this.messagesContent.scrollHeight;
    }

    addRawEvent(event) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'event';
        const headerDiv = document.createElement('div');
        headerDiv.className = 'event-header';
        headerDiv.innerHTML = `<span>${event.type}</span><span>▼</span>`;
        const contentDiv = document.createElement('div');
        contentDiv.className = 'event-content';
        contentDiv.style.display = 'none';
        contentDiv.textContent = JSON.stringify(event, null, 2);
        headerDiv.addEventListener('click', () => {
            const isHidden = contentDiv.style.display === 'none';
            contentDiv.style.display = isHidden ? 'block' : 'none';
            headerDiv.querySelector('span:last-child').textContent = isHidden ? '▲' : '▼';
        });
        eventDiv.appendChild(headerDiv);
        eventDiv.appendChild(contentDiv);
        this.eventsContent.appendChild(eventDiv);
        this.eventsContent.scrollTop = this.eventsContent.scrollHeight;
    }

    addToolEvent(event) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'event';
        let title = '';
        let description = '';
        if (event.type === 'handoff') {
            title = '🔄 Handoff';
            description = `${event.from} → ${event.to}`;
        } else if (event.type === 'tool_start') {
            title = `🛠️ Tool start: ${event.tool}`;
        } else if (event.type === 'tool_end') {
            title = `✅ Tool end: ${event.tool}`;
            if (event.output) {
                description = `${event.output}`;
            }
        }
        const headerDiv = document.createElement('div');
        headerDiv.className = 'event-header';
        headerDiv.textContent = title;
        const contentDiv = document.createElement('div');
        contentDiv.className = 'event-content';
        contentDiv.textContent = description;
        eventDiv.appendChild(headerDiv);
        eventDiv.appendChild(contentDiv);
        this.toolsContent.appendChild(eventDiv);
        this.toolsContent.scrollTop = this.toolsContent.scrollHeight;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new RealtimeLog();
});

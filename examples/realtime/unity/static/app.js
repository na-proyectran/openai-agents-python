class RealtimeLog {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.sessionId = null;
        this.status = document.getElementById('status');
        this.sessionSelect = document.getElementById('sessionSelect');
        this.refreshBtn = document.getElementById('refreshBtn');
        this.messagesContent = document.getElementById('messagesContent');
        this.eventsContent = document.getElementById('eventsContent');
        this.toolsContent = document.getElementById('toolsContent');

        this.refreshBtn.addEventListener('click', () => this.fetchSessions());
        this.sessionSelect.addEventListener('change', () => {
            const selected = this.sessionSelect.value;
            if (selected) {
                this.connect(selected);
            } else {
                this.disconnect();
            }
        });

        this.fetchSessions();
    }

    async fetchSessions() {
        try {
            const response = await fetch('/sessions');
            const data = await response.json();
            const sessions = data.sessions || [];
            const current = this.sessionSelect.value;
            this.sessionSelect.innerHTML = '<option value="">Select session</option>';
            sessions.forEach((id) => {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = id;
                this.sessionSelect.appendChild(option);
            });
            if (current && sessions.includes(current)) {
                this.sessionSelect.value = current;
            } else if (!sessions.includes(this.sessionId)) {
                this.disconnect();
            }
        } catch (err) {
            console.error('Failed to fetch sessions', err);
        }
    }

    connect(sessionId) {
        if (this.ws) {
            this.ws.close();
        }
        this.sessionId = sessionId;
        this.ws = new WebSocket(`ws://${location.host}/ws/${sessionId}`);
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
            this.ws = null;
        }
        this.isConnected = false;
        this.sessionId = null;
        this.updateUI();
    }

    updateUI() {
        if (this.isConnected && this.sessionId) {
            this.status.textContent = `Connected: ${this.sessionId}`;
            this.status.className = 'status connected';
        } else {
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

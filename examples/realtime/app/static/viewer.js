let ws = null;

async function fetchSessions() {
  const res = await fetch('/sessions');
  const sessions = await res.json();
  const select = document.getElementById('sessionSelect');
  select.innerHTML = '';
  sessions.forEach(id => {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = id;
    select.appendChild(opt);
  });
}

function connect() {
  const sessionId = document.getElementById('sessionSelect').value;
  if (!sessionId) {
    return;
  }
  if (ws) {
    ws.close();
  }
  ws = new WebSocket(`ws://${location.host}/watch/${sessionId}`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'history_updated' || data.type === 'history_snapshot') {
      renderHistory(data.history);
    }
  };
}

function renderHistory(history) {
  const container = document.getElementById('transcripts');
  container.textContent = '';
  history.forEach(item => {
    const texts = (item.content || [])
      .filter(c => c.type === 'text')
      .map(c => c.text)
      .join(' ');
    const line = document.createElement('div');
    line.textContent = `${item.role}: ${texts}`;
    container.appendChild(line);
  });
  container.scrollTop = container.scrollHeight;
}

document.getElementById('refreshBtn').addEventListener('click', fetchSessions);
document.getElementById('connectBtn').addEventListener('click', connect);

document.addEventListener('DOMContentLoaded', fetchSessions);

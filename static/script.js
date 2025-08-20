const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// WebSocket with session_id
const ws = new WebSocket(`ws://${window.location.host}/ws/${session_id}`);

ws.onopen = () => console.log("Connected to server.");

ws.onmessage = (event) => {
    const p = document.createElement('p');
    p.className = 'assistant';
    p.innerHTML = event.data;
    chatBox.appendChild(p);
    chatBox.scrollTop = chatBox.scrollHeight;
};

ws.onerror = (event) => {
    const p = document.createElement('p');
    p.className = 'system';
    p.innerHTML = "<b>System:</b> WebSocket error occurred.";
    chatBox.appendChild(p);
};

ws.onclose = () => {
    const p = document.createElement('p');
    p.className = 'system';
    p.innerHTML = "<b>System:</b> Connection closed.";
    chatBox.appendChild(p);
};

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Display user message
    const p = document.createElement('p');
    p.className = 'user';
    p.innerHTML = message;
    chatBox.appendChild(p);
    chatBox.scrollTop = chatBox.scrollHeight;

    ws.send(message);  // Send to WebSocket
    userInput.value = '';
}

sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        sendMessage();
    }
});

let socket = io();
let currentRoom = "General";
let username = document.getElementById('username').textContent;
let roomMessages = {};

// ---------------- Socket Event Listeners ----------------

// On connection, join default room
socket.on('connect', () => {
    joinRoom(currentRoom);
});

// General messages
socket.on('message', (data) => {
    addMessage(
        data.username,
        data.msg,
        data.username === username ? 'own' : 'other'
    );
});

// Private messages
socket.on('private_message', (data) => {
    addMessage(data.from, `[Private] ${data.msg}`, 'private');
});

// Status updates (system messages)
socket.on('status', (data) => {
    addMessage('System', data.msg, 'status');
});

// Active users list
socket.on('active_users', (data) => {
    const userList = document.getElementById('active-users');
    userList.innerHTML = data.users.map(
        (user) =>
            `<div class="active-user" onclick="insertPrivateMessage('${user}')">
                <img src="https://via.placeholder.com/30" alt="Avatar">
                ${user} ${user === username ? '(you)' : ''}
            </div>`
    ).join('');
});

// ---------------- Functions ----------------

// Add a message to chat
function addMessage(sender, message, type) {
    if (!roomMessages[currentRoom]) {
        roomMessages[currentRoom] = [];
    }

    roomMessages[currentRoom].push({ sender, message, type });

    const chat = document.getElementById('chat');
    const messageDiv = document.createElement('div');

    messageDiv.className = `message ${type}`;
    messageDiv.textContent = `${sender}: ${message}`;

    chat.appendChild(messageDiv);
    chat.scrollTop = chat.scrollHeight;
}

// Send a message
function sendMessage() {
    const input = document.getElementById('message');
    const message = input.value.trim();

    if (!message) return;

    if (message.startsWith('/')) {
        if (message.startsWith('@')) {
            const [target, ...msgParts] = message.split(' ');
            const privateMsg = msgParts.join(' ');

            if (privateMsg) {
                socket.emit('private_message', {
                    msg: privateMsg,
                    target: target.replace('@', '')
                });
                addMessage(username, `[Private] ${privateMsg}`, 'private');
            }
        }
    } else {
        socket.emit('message', {
            msg: message,
            room: currentRoom,
        });
        addMessage(username, message, 'own');
    }

    input.value = '';
    input.focus();
}

// Join a room
function joinRoom(room) {
    if (currentRoom) {
        socket.emit('leave', { room: currentRoom });
        document.querySelectorAll('.room-item').forEach((item) => {
            item.classList.remove('active-room');
        });
    }

    currentRoom = room;
    socket.emit('join', { room });

    document.querySelectorAll('.room-item').forEach((item) => {
        if (item.textContent.trim() === currentRoom) {
            item.classList.add('active-room');
        }
    });

    const chat = document.getElementById('chat');
    chat.innerHTML = "";

    if (roomMessages[room]) {
        roomMessages[room].forEach((msg) => {
            addMessage(msg.sender, msg.message, msg.type);
        });
    }
}

// Insert private message starter
function insertPrivateMessage(user) {
    const input = document.getElementById('message');
    input.value = `@${user} `;
    input.focus();
}

// Handle enter key for sending messages
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Initialize chat UI after DOM loads
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.room-item').forEach((item) => {
        if (item.textContent.trim() === currentRoom) {
            item.classList.add('active-room');
        }

        item.addEventListener('click', () => {
            joinRoom(item.textContent.trim());
        });
    });

    const messageInput = document.getElementById('message');
    messageInput.addEventListener('keypress', handleKeyPress);

    const sendBtn = document.getElementById('send-btn');
    sendBtn.addEventListener('click', sendMessage);
});





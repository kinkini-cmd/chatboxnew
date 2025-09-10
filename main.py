import os
import random
import logging
from datetime import datetime
from typing import Dict
from collections import defaultdict, deque

from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.middleware.proxy_fix import ProxyFix

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24)
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # Chat rooms
    CHAT_ROOMS = [
        "General",
        "Study Group",
        "Coding Corner",
        "Music Lovers"
    ]


app = Flask(__name__)
app.config.from_object(Config)

# Handle Reverse Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set up Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins=app.config["CORS_ORIGINS"],
    logger=True,
    engineio_logger=True
)

# Active users dict
active_users: Dict[str, dict] = {}

# Room history (last 5 messages per room)
room_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5))


# Generate guest username
def generate_guest_username() -> str:
    timestamp = datetime.now().strftime("%H%M%S")
    return f"Guest{timestamp}{random.randint(1000, 9999)}"


# Home Route
@app.route("/")
def index():
    if "username" not in session:
        session["username"] = generate_guest_username()
        logger.info(f"New user session made: {session['username']}")

    return render_template(
        "index.html",
        username=session["username"],
        rooms=app.config["CHAT_ROOMS"]
    )


# SocketIO connect event
@socketio.event
def connect():
    try:
        if "username" not in session:
            session["username"] = generate_guest_username()

        active_users[request.sid] = {
            "username": session["username"],
            "connected_at": datetime.now().isoformat()
        }

        emit("active_users", {
            "users": [user["username"] for user in active_users.values()]
        }, broadcast=True)

        logger.info(f"User connected: {session['username']}")

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


# SocketIO disconnect event
@socketio.event
def disconnect():
    try:
        if request.sid in active_users:
            username = active_users[request.sid]["username"]
            del active_users[request.sid]

            emit("active_users", {
                "users": [user["username"] for user in active_users.values()]
            }, broadcast=True)

            logger.info(f"User disconnected: {username}")

    except Exception as e:
        logger.error(f"Disconnection error: {str(e)}")


@socketio.on("join")
def on_join(data: dict):
    try:
        username = session["username"]
        room = data.get("room")

        if room not in app.config["CHAT_ROOMS"]:
            emit("error", {"message": "Invalid room."})
            return

        join_room(room)
        active_users[request.sid]["room"] = room

        # Send last 5 messages (history) to the joining user
        if room_history[room]:
            emit("history", list(room_history[room]), room=request.sid)

        # Notify others
        emit("status", {
            "msg": f"{username} has entered the room.",
            "type": "join",
            "timestamp": datetime.now().isoformat()
        }, room=room)

        logger.info(f"User {username} has joined {room}")

    except Exception as e:
        logger.error(str(e))


@socketio.on("leave")
def on_leave(data: dict):
    try:
        username = session["username"]
        room = data.get("room")

        leave_room(room)
        if request.sid in active_users:
            active_users[request.sid].pop("room", None)

        emit("status", {
            "msg": f"{username} has left the room.",
            "type": "leave",
            "timestamp": datetime.now().isoformat()
        }, room=room)

        logger.info(f"User {username} has left {room}")

    except Exception as e:
        logger.error(str(e))


@socketio.on("message")
def handle_messages(data: dict):
    try:
        username = session["username"]
        room = data.get("room")
        msg_type = data.get("type", "message")
        message = data.get("msg", "").strip()

        if not message:
            return

        timestamp = datetime.now().isoformat()

        if msg_type == "private":
            target_username = data.get("target")
            if not target_username:
                emit("error", {"message": "No target user specified."}, room=request.sid)
                return

            for sid, user_data in active_users.items():
                if user_data["username"] == target_username:
                    emit("private_message", {
                        "msg": message,
                        "from": username,
                        "to": target_username,
                        "timestamp": timestamp
                    }, room=sid)
                    logger.info(f"Private message from {username} to {target_username}: {message}")
                    return

            emit("error", {"message": f"User {target_username} not found."}, room=request.sid)

        else:
            if room not in app.config["CHAT_ROOMS"]:
                return

            msg_obj = {
                "msg": message,
                "username": username,
                "room": room,
                "timestamp": timestamp
            }

            # Save to history
            room_history[room].append(msg_obj)

            # Broadcast message
            emit("message", msg_obj, room=room)

            logger.info(f"[{room}] {username}: {message}")

    except Exception as e:
        logger.error(str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=app.config["DEBUG"],
        use_reloader=app.config["DEBUG"]
    )

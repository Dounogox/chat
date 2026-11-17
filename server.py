#!/usr/bin/env python3
"""Web server for chat application using Flask-SocketIO."""
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import base64
from datetime import datetime
import subprocess
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")
clients = {}
rooms = {}
UPLOAD_DIR = "uploaded_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/')
def index():
    """Serve the chat page."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"[CONNECT] SID={request.sid}")

def enter_chat_room(name, room_name):
    join_room(room_name)
    clients[request.sid] = {'name': name, 'room': room_name}

    print(f"[JOIN] {name} vào {room_name} ({request.sid})")
    emit('room_joined', {'name': name, 'room': room_name})
    emit('message', {'data': f'Xin chào {name}! Bạn đang ở phòng {room_name}.'})
    socketio.emit(
        'message',
        {'data': f"{name} đã tham gia phòng chat!"},
        to=room_name,
        include_self=False
    )


@socketio.on('create_room')
def handle_create_room(data):
    name = data.get('name', '').strip()
    room_name = data.get('room', '').strip()
    password = data.get('password', '')

    if not name or not room_name or not password:
        emit('room_error', {'message': 'Vui lòng nhập đầy đủ tên, tên phòng và mật khẩu.'})
        return
    if room_name in rooms:
        emit('room_error', {'message': 'Tên phòng đã tồn tại.'})
        return

    rooms[room_name] = generate_password_hash(password)
    enter_chat_room(name, room_name)


@socketio.on('join_room')
def handle_join_room(data):
    name = data.get('name', '').strip()
    room_name = data.get('room', '').strip()
    password = data.get('password', '')

    if not name or not room_name or not password:
        emit('room_error', {'message': 'Vui lòng nhập đầy đủ tên, tên phòng và mật khẩu.'})
        return
    if room_name not in rooms:
        emit('room_error', {'message': 'phòng chat không tồn tại'})
        return
    password_matches = check_password_hash(rooms[room_name], password)
    print(f"[ROOM AUTH] room={room_name!r}, password_matches={password_matches}")
    if not password_matches:
        emit('room_error', {'message': 'Sai mật khẩu'})
        return

    enter_chat_room(name, room_name)

@socketio.on('message')
def handle_message(data):
    if request.sid not in clients:
        print(f"[WARN] Unregistered SID gửi message: {request.sid}")
        return

    client = clients[request.sid]
    name = client['name']
    room_name = client['room']
    msg = data.get('message', '')

    print(f"[MESSAGE] {name}: {msg}")

    if msg == "{quit}":
        disconnect_user(request.sid)
    else:
        socketio.emit('message', {'data': f"{name}: {msg}"}, to=room_name)

@socketio.on('image')
def handle_image(data):
    if request.sid not in clients or not data.get('imageData'):
        return

    client = clients[request.sid]
    name = client['name']
    room_name = client['room']
    image_data = data.get('imageData')
    file_name = data.get('fileName', 'image')

    try:
        # imageData dạng: data:image/png;base64,AAAA...
        header, encoded = image_data.split(',', 1)

        # lấy extension từ header
        ext = header.split('/')[1].split(';')[0]

        # decode base64
        binary = base64.b64decode(encoded)

        # tạo tên file unique
        ts = datetime.now().strftime("%f")
        safe_name = f"{name}_{ts}.{ext}"
        path = os.path.join(UPLOAD_DIR, safe_name)

        # ghi file
        with open(path, "wb") as f:
            f.write(binary)

        print(f"[IMAGE SAVED] {safe_name}")

    except Exception as e:
        print(f"[IMAGE ERROR] {e}")
        return

    # broadcast cho client 
    socketio.emit('message', {
        'data': f"{name} đã gửi một hình ảnh:",
        'type': 'image',
        'imageData': image_data,
        'fileName': file_name
    }, to=room_name)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in clients:
        disconnect_user(request.sid)

def disconnect_user(sid):
    if sid in clients:
        client = clients[sid]
        name = client['name']
        room_name = client['room']
        print(f"[DISCONNECT] {name} ({sid})")
        leave_room(room_name, sid=sid)
        del clients[sid]
        socketio.emit(
            'message',
            {'data': f"{name} đã thoát phòng chat."},
            to=room_name
        )

if __name__ == '__main__':

    print("Web server đang chạy")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


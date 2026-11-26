#!/usr/bin/env python3
"""Socket.IO backend for the Brotherhood desktop app."""
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import base64
import mimetypes
import subprocess
import uuid
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    max_http_buffer_size=150 * 1024 * 1024,
)
clients = {}
rooms = {}
UPLOAD_DIR = "uploaded_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

    if msg == "{quit}":
        disconnect_user(request.sid)
    else:
        socketio.emit('message', {'data': f"{name}: {msg}"}, to=room_name)

def handle_media(data, media_type):
    data_key = 'imageData' if media_type == 'image' else 'videoData'
    if request.sid not in clients or not isinstance(data.get(data_key), str):
        return

    client = clients[request.sid]
    name = client['name']
    room_name = client['room']
    media_data = data[data_key]
    file_name = data.get('fileName', media_type)
    max_size = 100 * 1024 * 1024 if media_type == 'video' else 5 * 1024 * 1024

    try:
        header, encoded = media_data.split(',', 1)
        mime_type = header[5:].split(';', 1)[0].lower()
        if not header.lower().endswith(';base64') or not mime_type.startswith(f'{media_type}/'):
            raise ValueError('Invalid media type')
        if len(encoded) > ((max_size + 2) // 3) * 4:
            raise ValueError('Media exceeds size limit')
        binary = base64.b64decode(encoded, validate=True)
        if not binary or len(binary) > max_size:
            raise ValueError('Media exceeds size limit')

        extension = mimetypes.guess_extension(mime_type, strict=False) or '.bin'
        safe_name = f'{uuid.uuid4().hex}{extension}'
        path = os.path.join(UPLOAD_DIR, safe_name)
        with open(path, "wb") as f:
            f.write(binary)

    except (OSError, ValueError) as error:
        print(f"[MEDIA ERROR] {error}")
        return

    socketio.emit('message', {
        'data': f"{name} đã gửi một {'video' if media_type == 'video' else 'hình ảnh'}:",
        'type': media_type,
        data_key: media_data,
        'fileName': file_name,
        'fileType': mime_type,
    }, to=room_name)


@socketio.on('image')
def handle_image(data):
    handle_media(data, 'image')


@socketio.on('video')
def handle_video(data):
    handle_media(data, 'video')

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
    print("Socket.IO backend đang chạy")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


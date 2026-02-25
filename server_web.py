#!/usr/bin/env python3
"""Web server for chat application using Flask-SocketIO."""
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
import os
import base64
from datetime import datetime
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")
clients = {}
UPLOAD_DIR = "uploaded_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/')
def index():
    """Serve the chat page."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"[CONNECT] SID={request.sid}")

@socketio.on('register')
def handle_register(data):
    name = data.get('name', 'Anonymous')
    clients[request.sid] = name

    print(f"[REGISTER] {name} ({request.sid})")

    emit('message', {'data': f'Xin chào {name}!'})
    socketio.emit('message', {'data': f"{name} đã tham gia phòng chat!"}, include_self=False)

@socketio.on('message')
def handle_message(data):
    if request.sid not in clients:
        print(f"[WARN] Unregistered SID gửi message: {request.sid}")
        return

    name = clients[request.sid]
    msg = data.get('message', '')

    print(f"[MESSAGE] {name}: {msg}")

    if msg == "{quit}":
        disconnect_user(request.sid, name)
    else:
        socketio.emit('message', {'data': f"{name}: {msg}"})

@socketio.on('image')
def handle_image(data):
    if request.sid not in clients or not data.get('imageData'):
        return

    name = clients[request.sid]
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
    })

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in clients:
        disconnect_user(request.sid, clients[request.sid])

def disconnect_user(sid, name):
    if sid in clients:
        print(f"[DISCONNECT] {name} ({sid})")
        del clients[sid]
        socketio.emit('message', {'data': f"{name} đã thoát phòng chat."})

if __name__ == '__main__':

    subprocess.Popen(
    ['cmd', '/k', 'Link chat.bat'],
    creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    print("Web server đang chạy")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


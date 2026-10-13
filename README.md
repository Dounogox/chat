# Brotherhood Chat

Ứng dụng desktop dùng giao diện Qt native và Socket.IO để kết nối trực tiếp tới
`server_web.py`. File `.exe` là client; máy chủ chat phải được chạy riêng trên
một máy mà những người tham gia có thể truy cập.

## Build `.exe` trên Windows

Cài Python 3.10 trở lên. Mở Command Prompt tại thư mục dự án và chạy:

```bat
build_windows.bat
```

Script tạo môi trường build, cài dependency và xuất `dist\Brotherhood.exe`.
Build cần chạy trên Windows; PyInstaller không tạo file Windows từ Linux.

## Chạy client từ mã nguồn

Trong PowerShell:

```powershell
py -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-desktop\Scripts\python.exe desktop_app.py
```

Trong ứng dụng, nhập địa chỉ server, ví dụ `http://192.168.1.20:5000`, rồi
nhập tên để kết nối, tạo phòng hoặc tham gia phòng.

## Chạy server

Trên máy chủ, cài Python và các dependency của dự án, sau đó chạy:

```bash
python -m pip install -r requirements.txt
python server_web.py
```

Server lắng nghe trên cổng `5000` và các giao diện mạng của máy. Mở TCP cổng
`5000` trong firewall nếu client kết nối qua mạng LAN. Để dùng qua Internet,
triển khai server trên máy chủ có thể truy cập công khai và cấu hình HTTPS; không
nên đưa server phát triển trực tiếp ra Internet.

## Chạy phiên bản web

```bash
python server_web.py
```

Mở `http://localhost:5000` trên trình duyệt.
# Fetch — tải video Google Drive về máy

Dán nhiều link Google Drive, chọn thư mục lưu, tải video về máy.
Mỗi link được tải vào **một thư mục riêng**, tải **song song** và hiện **tiến trình từng video**.

---

## Dành cho người không rành kỹ thuật

👉 **Xem file [HUONG-DAN-CAI-DAT.md](HUONG-DAN-CAI-DAT.md)** — hướng dẫn từng bước: cài Python 3,
rồi bấm đúp chạy `Start-macOS.command` (macOS) hoặc `Start-Windows.bat` (Windows).

Tóm tắt 3 bước:

1. Cài **Python 3** từ https://www.python.org/downloads/ (Windows nhớ tích **Add python.exe to PATH**).
2. Tải project này về (**Code → Download ZIP**) rồi giải nén.
3. Bấm đúp file khởi chạy — trình duyệt tự mở trang của tool.

> Giữ cửa sổ đen (Terminal / Command Prompt) luôn mở trong lúc dùng; đóng nó là tool dừng.

---

## Cách dùng

1. **Thư mục lưu** — đã tự điền sẵn `Downloads`. Muốn đổi thì bấm **Chọn…**.
2. **Links** — dán mỗi dòng một link Google Drive (link folder hoặc link file).
3. **Xem danh sách** (không bắt buộc) — đọc trước để biết mỗi link có bao nhiêu
   video và tên từng video, tránh tải nhầm.
4. **Tải về** — chọn `Tất cả video`, hoặc `Giới hạn số lượng` rồi nhập số video
   mỗi link (ví dụ lấy 5 video đầu của mỗi thư mục).
5. Bấm **Bắt đầu tải** và theo dõi tiến trình từng video. Bấm **Hủy** để dừng;
   lần sau bấm lại sẽ **tải tiếp** từ chỗ đã dừng.

Các tuỳ chọn khác:

- **Chất lượng**: 720p (nét hơn) hoặc 360p (nhẹ hơn). File mp4 đã có sẵn cả hình và tiếng.
- **Tải cùng lúc**: số video tải song song (1–8). Mạng yếu thì để 2–3.

**Lưu ý quan trọng:** link phải được chia sẻ ở chế độ **“Bất kỳ ai có liên kết”**.
Nếu để riêng tư, tool sẽ báo lỗi không lấy được video.

Kết quả:

```
<Thư mục lưu>/
├── Chương 1 - GIAO ĐOẠN PHÁT ÂM/     ← link folder #1
│   ├── Bài 1 Phát âm phụ âm.mp4
│   ├── Bài 2 Phát âm nguyên âm.mp4
│   └── Bài 3 Phát âm ED SES.mp4
└── Bài 3 Phát âm ED SES/             ← link file #2
    └── Bài 3 Phát âm ED SES.mp4
```

---

## Dành cho người kỹ thuật

### Chạy trực tiếp

```bash
python3 server.py                 # mở http://127.0.0.1:8000
python3 server.py --port 9000     # đổi cổng
python3 server.py --no-browser    # không tự mở trình duyệt
python3 server.py --host 0.0.0.0  # cho máy khác trong LAN truy cập
```

Nếu cổng đang bận, tool tự nhảy sang cổng kế tiếp. Không cần cài thêm gì (chỉ Python 3 standard library).

### Cách hoạt động

Giống thao tác thủ công qua DevTools (F12), nhưng tự động:

1. **Liệt kê folder** — đọc `https://drive.google.com/embeddedfolderview?id=<id>#list`
   để lấy danh sách file (id, tên, mime).
2. **Lấy metadata phát lại** — gọi endpoint Drive player:
   `https://workspacevideo-pa.clients6.google.com/v1/drive/media/<id>/playback?auditContext=forDisplay&key=<API_KEY>`
   → JSON chứa `formatStreamingData.progressiveTranscodes`.
3. **Chọn itag** — tìm `itag = 22` (720p, mp4, có tiếng). Không có thì fallback sang
   itag 18 / progressive phân giải cao nhất.
4. **Tải về** — tải URL `videoplayback` với hỗ trợ `Range` (resume), chạy song song
   qua thread pool, tiến trình đẩy về UI bằng Server-Sent Events.

Lưu ý kỹ thuật: `contentLength` trong JSON metadata của `progressiveTranscodes` đôi khi sai
(ví dụ ghi 1.2 MB cho file 172 MB), nên tool luôn lấy dung lượng thật từ header
`Content-Range` của server.

### Giới hạn

- Folder/file phải ở chế độ **“Bất kỳ ai có liên kết”** (các endpoint công khai, không cần đăng nhập).
- Chỉ liệt kê file ở **cấp đầu** của folder (không đi sâu vào folder con).
- Video phải đã được Google xử lý xong (`AVAILABLE`); nếu chưa transcode sẽ báo lỗi.
- Chọn thư mục dùng hộp thoại native: `osascript` (macOS), PowerShell (Windows).
  Không mở được thì gõ tay đường dẫn.

### Cấu trúc

| File | Vai trò |
|------|---------|
| `server.py` | HTTP server, API (`/api/config`, `/api/preview`, `/api/pick-folder`, `/api/start`, `/api/cancel`), SSE tiến trình |
| `gdrive.py` | Logic Google Drive: parse link, liệt kê folder, playback, chọn itag, tải file |
| `static/` | Giao diện web (`index.html`, `app.js`, `style.css`) |
| `Start-macOS.command`, `Start-Windows.bat` | File bấm đúp để khởi chạy |
| `HUONG-DAN-CAI-DAT.md` | Hướng dẫn cài đặt cho người không rành kỹ thuật |

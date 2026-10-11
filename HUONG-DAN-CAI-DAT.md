# Hướng dẫn cài đặt và chạy Fetch

Làm theo đúng thứ tự dưới đây. Tổng cộng khoảng 5 phút, chỉ làm một lần.

Cần chuẩn bị:

- Một máy **macOS** hoặc **Windows**.
- Một trình duyệt (Safari, Chrome, Edge… — máy nào cũng có sẵn).

---

## Bước 1 — Cài Python 3

Fetch chạy bằng Python, nên cần cài Python 3 trước. **Không cần biết lập trình**, chỉ cần bấm vài nút.

### Nếu bạn dùng Windows

1. Mở trình duyệt, vào **https://www.python.org/downloads/**
2. Bấm nút vàng lớn **Download Python 3.x.x**.
3. Mở file vừa tải (thường nằm trong thư mục **Downloads**).
4. ⚠️ **Rất quan trọng:** ở màn hình đầu tiên của bộ cài, tích vào ô
   **“Add python.exe to PATH”** ở dưới cùng, rồi mới bấm **Install Now**.
   (Bỏ qua bước này thì tool sẽ không chạy được.)
5. Đợi cài xong, bấm **Close**.

**Kiểm tra:** bấm phím Windows, gõ `cmd` rồi Enter để mở **Command Prompt**, gõ:

```
python --version
```

Nếu hiện ra dòng kiểu `Python 3.12.1` là đã xong. Nếu báo *“không nhận diện được”*,
hãy cài lại và nhớ tích **Add python.exe to PATH**.

### Nếu bạn dùng macOS

1. Mở trình duyệt, vào **https://www.python.org/downloads/**
2. Bấm nút vàng lớn **Download Python 3.x.x** (bản cho macOS).
3. Mở file vừa tải, bấm **Continue** → **Continue** → **Install** → nhập mật khẩu máy → **Install Software**.
4. Đợi cài xong, bấm **Close**.

**Kiểm tra:** mở **Terminal** (bấm `Cmd + Space`, gõ `Terminal`, Enter), gõ:

```
python3 --version
```

Nếu hiện ra dòng kiểu `Python 3.12.1` là đã xong.

---

## Bước 2 — Tải Fetch về máy

1. Mở trang project này trên GitHub.
2. Bấm nút xanh **Code** → **Download ZIP**.
3. Giải nén file ZIP vừa tải (bấm đúp vào file ZIP, hoặc chuột phải → **Extract All** trên Windows).
   Bạn sẽ được một thư mục tên kiểu `DownloadVideoGoogleDrive-main`.

> **Windows:** nếu khi giải nén bị chặn, hãy chuột phải vào file ZIP → **Properties** →
> tích **Unblock** ở dưới cùng → **OK**, rồi giải nén lại.

Đặt thư mục này ở chỗ dễ tìm, ví dụ **Desktop**.

---

## Bước 3 — Chạy Fetch

Mở thư mục vừa giải nén, rồi:

### Trên macOS

- Bấm đúp vào file **`Start-macOS.command`**.
- Một cửa sổ đen (Terminal) hiện ra, sau đó **trình duyệt tự mở** trang của tool.

**Nếu macOS chặn** (*“không thể mở vì không rõ nguồn gốc”*), làm một trong hai cách:

- **Cách 1:** chuột phải vào `Start-macOS.command` → **Open** → bấm **Open** một lần nữa.
- **Cách 2** (macOS mới, không thấy nút Open): mở **System Settings → Privacy & Security**,
  kéo xuống tìm dòng về `Start-macOS.command` và bấm **Open Anyway**.
- **Cách 3** (nếu vẫn báo *“cannot be executed”*): mở **Terminal**, gõ `chmod +x ` (có dấu cách ở cuối),
  rồi **kéo file `Start-macOS.command` vào cửa sổ Terminal**, Enter. Sau đó bấm đúp lại file.

### Trên Windows

- Bấm đúp vào file **`Start-Windows.bat`**.
- Một cửa sổ đen (Command Prompt) hiện ra, sau đó **trình duyệt tự mở** trang của tool.

---

## Bước 4 — Dùng Fetch

Trình duyệt sẽ mở trang **http://127.0.0.1:8000** (đây là tool chạy ngay trên máy bạn).

1. **Thư mục lưu** — đã tự điền sẵn `Downloads`. Muốn đổi thì bấm **Chọn…**.
2. **Links** — dán link Google Drive, mỗi dòng một link.
3. **Xem danh sách** *(không bắt buộc)* — xem trước mỗi link có bao nhiêu video.
4. **Tải về** — chọn `Tất cả video`, hoặc `Giới hạn số lượng` để lấy một số video nhất định.
5. Bấm **Bắt đầu tải** và theo dõi tiến trình từng video.

> **Quan trọng:** link phải được chia sẻ ở chế độ **“Bất kỳ ai có liên kết”** thì tool mới đọc được.

**Để dừng tool:** đóng cửa sổ đen (Terminal / Command Prompt). Trong lúc tải, **giữ cửa sổ đen
luôn mở**; đóng nó là tool dừng ngay.

---

## Khi có trục trặc

| Hiện tượng | Cách xử lý |
|---|---|
| Cửa sổ đen hiện *“Chưa tìm thấy Python 3”* | Chưa cài Python, hoặc cài mà quên tích **Add python.exe to PATH**. Làm lại **Bước 1**. |
| `python --version` báo lỗi trên Windows | Cài lại Python và tích **Add python.exe to PATH**. |
| macOS không cho mở `Start-macOS.command` | Xem 3 cách ở **Bước 3 → Trên macOS**. |
| `python3 --version` chạy được nhưng tool vẫn không mở | Chụp lại cửa sổ đen và gửi cho người đưa bạn tool này. |
| Trình duyệt không tự mở | Tự mở trình duyệt và vào địa chỉ **http://127.0.0.1:8000** |
| Báo *“Không tìm thấy video nào”* hoặc không tải được | Link chưa để chế độ **“Bất kỳ ai có liên kết”**. Vào Google Drive → chuột phải file/thư mục → **Share** → đổi thành **Anyone with the link**. |
| Đóng cửa sổ đen rồi mở lại, muốn tải tiếp | Mở lại tool rồi bấm **Bắt đầu tải** — tool sẽ tải tiếp từ chỗ đã dừng. |

Nếu vẫn không được, hãy chụp lại **cửa sổ đen** và gửi lại; thông báo lỗi trong đó là thứ
cần thiết để tìm ra nguyên nhân.

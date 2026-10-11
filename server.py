"""Local web app to download Google Drive videos.

Run:  python3 server.py
Then open http://127.0.0.1:8000

The server is a thin layer on top of gdrive.py: it serves a small SPA, exposes
a few JSON endpoints and streams download progress over Server-Sent Events.
Standard library only.
"""

import argparse
import json
import mimetypes
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gdrive

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

JOBS = {}
JOBS_LOCK = threading.Lock()


# --------------------------------------------------------------------------- #
# Job model (progress fan-out to SSE subscribers)
# --------------------------------------------------------------------------- #
class Job:
    def __init__(self, job_id):
        self.id = job_id
        self._lock = threading.Lock()
        self._history = []
        self._subscribers = []
        self.cancelled = threading.Event()
        self.done = False

    def emit(self, event):
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except Exception:
                pass
        if event.get("type") in ("done", "aborted"):
            self.done = True

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            for event in self._history:
                q.put_nowait(event)
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


# --------------------------------------------------------------------------- #
# Download worker
# --------------------------------------------------------------------------- #
def unique_dir(base, name, used):
    safe = gdrive.sanitize_name(name, "link")
    candidate = os.path.join(base, safe)
    n = 2
    while candidate in used:
        candidate = os.path.join(base, "%s (%d)" % (safe, n))
        n += 1
    used.add(candidate)
    return candidate


def collect_videos(folder_id):
    entries = gdrive.list_folder(folder_id)
    return [{"id": e["id"], "name": e["name"]} for e in entries if gdrive.is_video(e)]


def download_one(job, link_index, file_index, video, subdir, prefer_itag):
    if job.cancelled.is_set():
        return
    fid = video["id"]
    name = video["name"] or fid
    if not os.path.splitext(name)[1]:
        name += ".mp4"
    fname = gdrive.sanitize_name(name, fid + ".mp4")
    dest = os.path.join(subdir, fname)

    job.emit({"type": "file_start", "link": link_index, "file": file_index, "name": fname})
    try:
        playback = gdrive.get_playback(fid)
        url, _meta = gdrive.select_stream(playback, prefer_itag)
        if not url:
            job.emit({"type": "file_error", "link": link_index, "file": file_index,
                      "message": "Không có stream video phù hợp"})
            return

        def on_progress(done, total):
            job.emit({"type": "file_progress", "link": link_index, "file": file_index,
                      "downloaded": done, "total": total})

        status = gdrive.download(url, dest, on_progress, job.cancelled.is_set)
        job.emit({"type": "file_done", "link": link_index, "file": file_index,
                  "status": status, "path": dest})
    except gdrive.Cancelled:
        raise
    except Exception as exc:
        job.emit({"type": "file_error", "link": link_index, "file": file_index,
                  "message": str(exc)})


def resolve_link(url):
    """Turn a Drive link into (folder_name, [{id, name}, ...])."""
    kind, fid = gdrive.classify_link(url)
    if kind == "folder":
        name = gdrive.folder_name(fid) or ("folder_%s" % fid[:8])
        return name, collect_videos(fid)
    try:
        playback = gdrive.get_playback(fid)
        title = gdrive.media_title(playback) or fid
        return os.path.splitext(title)[0], [{"id": fid, "name": title}]
    except gdrive.NotMedia:
        if kind == "auto":
            name = gdrive.folder_name(fid) or ("folder_%s" % fid[:8])
            return name, collect_videos(fid)
        raise gdrive.GDriveError(
            "File này không phải video hoặc chưa được chia sẻ công khai."
        )


def run_job(job, links, output_dir, prefer_itag, max_workers, limit=0):
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as exc:
        job.emit({"type": "fatal", "message": "Không tạo được thư mục đích: %s" % exc})
        job.emit({"type": "done"})
        return

    # Phase 1: resolve every link up front so all cards (and their file rows)
    # exist before any download starts.
    used = set()
    remaining = {}
    tasks = []  # (link_index, file_index, video, subdir)

    for index, url in enumerate(links):
        if job.cancelled.is_set():
            break
        job.emit({"type": "link_start", "index": index, "url": url})
        try:
            name, videos = resolve_link(url)
            if limit > 0:
                videos = videos[:limit]
            if not videos:
                job.emit({"type": "link_error", "index": index,
                          "message": "Không tìm thấy video nào trong link này."})
                continue
            subdir = unique_dir(output_dir, name or ("link_%d" % (index + 1)), used)
            os.makedirs(subdir, exist_ok=True)
            job.emit({"type": "link_resolved", "index": index,
                      "name": os.path.basename(subdir), "folder": subdir,
                      "videos": [v["name"] for v in videos]})
            remaining[index] = len(videos)
            for file_index, video in enumerate(videos):
                tasks.append((index, file_index, video, subdir))
        except Exception as exc:
            job.emit({"type": "link_error", "index": index, "message": str(exc)})

    # Phase 2: download every file concurrently across all links.
    finished = set()
    if tasks and not job.cancelled.is_set():
        workers = max(1, min(max_workers, len(tasks)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(download_one, job, li, fi, video, subdir, prefer_itag): li
                for (li, fi, video, subdir) in tasks
            }
            for future in as_completed(futures):
                link_index = futures[future]
                try:
                    future.result()
                except Exception:
                    pass
                remaining[link_index] -= 1
                if remaining[link_index] <= 0:
                    finished.add(link_index)
                    event = "link_aborted" if job.cancelled.is_set() else "link_done"
                    job.emit({"type": event, "index": link_index})

    if job.cancelled.is_set():
        for link_index in remaining:
            if link_index not in finished:
                finished.add(link_index)
                job.emit({"type": "link_aborted", "index": link_index})

    job.emit({"type": "aborted" if job.cancelled.is_set() else "done"})
    # Drop the job shortly after it finishes if nobody is watching it.
    threading.Timer(120, lambda: JOBS.pop(job.id, None)).start()


# --------------------------------------------------------------------------- #
# Folder picker (native macOS / Windows dialogs, run as a separate process so
# nothing GUI-related touches the request threads)
# --------------------------------------------------------------------------- #
def pick_folder_dialog():
    if sys.platform == "darwin":
        return _pick_macos()
    if sys.platform.startswith("win"):
        return _pick_windows()
    raise gdrive.GDriveError(
        "Chưa hỗ trợ hệ điều hành này. Hãy nhập đường dẫn thủ công."
    )


def _run_picker(cmd, timeout=600):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        if isinstance(exc, FileNotFoundError):
            return None
        return None
    if result.returncode != 0:
        return None  # usually means the user cancelled
    path = result.stdout.strip().rstrip("/\\")
    return path or None


def _pick_macos():
    script = 'POSIX path of (choose folder with prompt "Chọn thư mục lưu video")'
    return _run_picker(["osascript", "-e", script])


def _pick_windows():
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description = 'Chọn thư mục lưu video'; "
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ Write-Output $d.SelectedPath }"
    )
    return _run_picker(["powershell", "-NoProfile", "-STA", "-Command", ps])


def default_output_dir():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(downloads):
        return downloads
    return os.path.expanduser("~")


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GDriveDL/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---- helpers ---------------------------------------------------------- #
    def _send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ---- routing ---------------------------------------------------------- #
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            return self._serve_static("index.html")
        if path == "/api/config":
            return self._send_json({"outputDir": default_output_dir(),
                                    "platform": sys.platform})
        if path == "/api/events":
            return self._serve_events()
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/preview":
            return self._api_preview()
        if path == "/api/pick-folder":
            return self._api_pick_folder()
        if path == "/api/start":
            return self._api_start()
        if path == "/api/cancel":
            return self._api_cancel()
        return self._send_json({"error": "not found"}, 404)

    # ---- static ----------------------------------------------------------- #
    def _serve_static(self, rel):
        safe = os.path.normpath(rel).lstrip("/\\")
        full = os.path.join(STATIC_DIR, safe)
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            return self._send_json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as handle:
            self._send_bytes(handle.read(), ctype)

    # ---- APIs ------------------------------------------------------------- #
    def _api_preview(self):
        body = self._read_json()
        links = [l.strip() for l in (body.get("links") or []) if l and l.strip()]
        if not links:
            return self._send_json({"ok": False, "error": "Chưa có link nào."}, 200)

        groups = [None] * len(links)

        def look(index, url):
            try:
                name, videos = resolve_link(url)
                groups[index] = {"url": url, "name": name,
                                 "videos": [v["name"] for v in videos]}
            except Exception as exc:
                groups[index] = {"url": url, "error": str(exc)}

        with ThreadPoolExecutor(max_workers=min(4, len(links))) as pool:
            list(pool.map(lambda pair: look(*pair), list(enumerate(links))))

        self._send_json({"ok": True, "groups": groups})

    def _api_pick_folder(self):
        try:
            path = pick_folder_dialog()
            self._send_json({"ok": True, "path": path})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 200)

    def _api_start(self):
        body = self._read_json()
        links = [l.strip() for l in (body.get("links") or []) if l and l.strip()]
        output_dir = (body.get("outputDir") or "").strip()
        try:
            prefer_itag = int(body.get("itag") or 22)
        except (TypeError, ValueError):
            prefer_itag = 22
        try:
            max_workers = int(body.get("concurrency") or 3)
        except (TypeError, ValueError):
            max_workers = 3
        max_workers = max(1, min(max_workers, 8))

        try:
            limit = int(body.get("limit") or 0)
        except (TypeError, ValueError):
            limit = 0
        limit = max(0, limit)

        if not links:
            return self._send_json({"ok": False, "error": "Chưa có link nào."}, 200)
        if not output_dir:
            return self._send_json({"ok": False, "error": "Chưa chọn thư mục lưu."}, 200)
        output_dir = os.path.expanduser(output_dir)

        job = Job(uuid.uuid4().hex[:12])
        with JOBS_LOCK:
            JOBS[job.id] = job
        thread = threading.Thread(
            target=run_job,
            args=(job, links, output_dir, prefer_itag, max_workers, limit),
            daemon=True,
        )
        thread.start()
        self._send_json({"ok": True, "jobId": job.id})

    def _api_cancel(self):
        body = self._read_json()
        with JOBS_LOCK:
            job = JOBS.get(body.get("jobId"))
        if job:
            job.cancelled.set()
        self._send_json({"ok": True})

    # ---- SSE -------------------------------------------------------------- #
    def _serve_events(self):
        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(self.path).query)
        job_id = (query.get("job") or [""])[0]
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            return self._send_json({"error": "job not found"}, 404)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = job.subscribe()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    if job.done:
                        break
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                self.wfile.write(("data: %s\n\n" % payload).encode("utf-8"))
                self.wfile.flush()
                if event.get("type") in ("done", "aborted"):
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            job.unsubscribe(q)
            with JOBS_LOCK:
                JOBS.pop(job.id, None)


def existing_instance(host, port):
    """True if our own server already answers on this port."""
    try:
        with urllib.request.urlopen("http://%s:%d/api/config" % (host, port), timeout=1.5) as resp:
            return b'"outputDir"' in resp.read(200)
    except Exception:
        return False


def serve(host, port, open_browser=True):
    """Serve the app. If an instance is already running, just open its tab."""
    if existing_instance(host, port):
        url = "http://%s:%d" % (host, port)
        print("Fetch đang chạy sẵn tại %s" % url, flush=True)
        if open_browser:
            webbrowser.open(url)
        return

    httpd = None
    for candidate in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer((host, candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit("Không mở được cổng kết nối. Hãy đóng bớt ứng dụng rồi thử lại.")

    httpd.daemon_threads = True
    url = "http://%s:%d" % (host, port)
    line = "=" * 52
    print(line, flush=True)
    print("  Fetch - Google Drive video downloader", flush=True)
    print("  Đang chạy tại: %s" % url, flush=True)
    print("  Giữ cửa sổ này mở trong lúc tải. Đóng cửa sổ để dừng.", flush=True)
    print(line, flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng. Bạn có thể đóng cửa sổ này.")
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Google Drive video downloader (web UI)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    args = parser.parse_args()
    try:
        serve(args.host, args.port, open_browser=not args.no_browser)
    except SystemExit:
        raise
    except Exception as exc:
        print("\nFetch gặp lỗi và không khởi động được: %s" % exc, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

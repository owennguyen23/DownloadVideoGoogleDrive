"""Google Drive video downloader core.

Resolves Google Drive links, lists videos inside a folder, reads the public
playback metadata the Drive web player uses, picks a progressive stream
(itag 22 = 720p mp4 with audio by default) and downloads it with resume
support and progress callbacks.

No third-party dependencies (Python 3 standard library only).
"""

import html as html_mod
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Public API key embedded in the Drive web player requests.
API_KEY = "AIzaSyD_InbmSFufIEps5UAt2NmB_3LvBH3Sz_8"
PLAYBACK_URL = (
    "https://workspacevideo-pa.clients6.google.com/v1/drive/media/{fid}/playback"
    "?auditContext=forDisplay&key={key}"
)
FOLDER_VIEW_URL = "https://drive.google.com/embeddedfolderview?id={fid}#list"
FOLDER_PAGE_URL = "https://drive.google.com/drive/folders/{fid}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

FOLDER_RE = re.compile(r"/folders/([A-Za-z0-9_-]{5,})")
FILE_D_RE = re.compile(r"/file/d/([A-Za-z0-9_-]{5,})")
ID_RE = re.compile(r"[?&]id=([A-Za-z0-9_-]{5,})")

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv")


class GDriveError(Exception):
    """Raised for expected, user-facing errors."""


class NotMedia(GDriveError):
    """Raised when a Drive item is not playable media (e.g. a folder)."""


class Cancelled(Exception):
    """Raised when a running job is cancelled."""


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _headers(extra=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra:
        headers.update(extra)
    return headers


def http_get(url, extra_headers=None, timeout=60):
    """GET a URL and return raw bytes. Raises GDriveError on HTTP failures."""
    req = urllib.request.Request(url, headers=_headers(extra_headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise GDriveError("HTTP %s cho %s: %s" % (exc.code, url, body[:300]))
    except urllib.error.URLError as exc:
        raise GDriveError("Không kết nối được tới Google: %s" % exc.reason)


def http_get_text(url, extra_headers=None, timeout=60):
    return http_get(url, extra_headers, timeout).decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# Link parsing & resolution
# --------------------------------------------------------------------------- #
def classify_link(url):
    """Return (kind, file_id) where kind is 'folder', 'file' or 'auto'."""
    url = (url or "").strip()
    if not url:
        raise GDriveError("Link rỗng")
    m = FOLDER_RE.search(url)
    if m:
        return "folder", m.group(1)
    m = FILE_D_RE.search(url)
    if m:
        return "file", m.group(1)
    m = ID_RE.search(url)
    if m:
        return "auto", m.group(1)
    raise GDriveError("Không nhận diện được link Google Drive: %s" % url)


def get_playback(file_id):
    """Fetch and parse the public playback metadata for a media file."""
    url = PLAYBACK_URL.format(fid=file_id, key=API_KEY)
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        if "not a media item" in body or exc.code == 404:
            raise NotMedia(body[:200])
        raise GDriveError("Playback HTTP %s: %s" % (exc.code, body[:200]))
    except urllib.error.URLError as exc:
        raise GDriveError("Không kết nối được tới Google: %s" % exc.reason)

    streaming = payload.get("mediaStreamingData")
    if not streaming or not streaming.get("formatStreamingData"):
        raise NotMedia("Không có dữ liệu streaming")
    return payload


def list_folder(folder_id):
    """List top-level entries of a shared folder. Returns list of dicts."""
    text = http_get_text(FOLDER_VIEW_URL.format(fid=folder_id))
    entries = []
    for block in re.split(r'<div class="flip-entry"', text)[1:]:
        id_match = re.search(r'id="entry-([^"]+)"', block)
        name_match = re.search(r'flip-entry-title">([^<]*)<', block)
        mime_match = re.search(r"/type/([^\"']+)", block)
        if not id_match:
            continue
        entries.append(
            {
                "id": id_match.group(1),
                "name": html_mod.unescape(name_match.group(1)) if name_match else "",
                "mime": mime_match.group(1) if mime_match else "",
            }
        )
    return entries


def folder_name(folder_id):
    """Best-effort folder name from the folder page title."""
    try:
        text = http_get_text(FOLDER_PAGE_URL.format(fid=folder_id))
    except GDriveError:
        return ""
    title = re.search(r"<title>(.*?)</title>", text, re.S)
    if not title:
        return ""
    name = html_mod.unescape(title.group(1)).strip()
    name = re.sub(r"\s*-\s*Google Drive\s*$", "", name)
    return name


def is_video(entry):
    mime = (entry.get("mime") or "").lower()
    name = (entry.get("name") or "").lower()
    return mime.startswith("video/") or name.endswith(VIDEO_EXTS)


# --------------------------------------------------------------------------- #
# Stream selection
# --------------------------------------------------------------------------- #
def select_stream(playback, prefer_itag=22):
    """Pick a progressive transcode. Returns (url, meta) or (None, None)."""
    fmt = playback["mediaStreamingData"]["formatStreamingData"]
    progressive = fmt.get("progressiveTranscodes") or []

    if prefer_itag:
        for item in progressive:
            if item.get("itag") == prefer_itag:
                return item.get("url"), item.get("transcodeMetadata", {})
        if prefer_itag != 18:
            # Requested itag not available: try the other common progressive one.
            for item in progressive:
                if item.get("itag") == 18:
                    return item.get("url"), item.get("transcodeMetadata", {})

    if progressive:
        def area(item):
            meta = item.get("transcodeMetadata", {})
            return (meta.get("width") or 0) * (meta.get("height") or 0)

        best = max(progressive, key=area)
        return best.get("url"), best.get("transcodeMetadata", {})

    return None, None


def media_title(playback):
    return playback.get("mediaMetadata", {}).get("title") or ""


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def sanitize_name(name, fallback="video"):
    name = (name or "").strip()
    name = name.replace("/", "_").replace("\\", "_").replace(":", " -")
    name = re.sub(r"[\x00-\x1f]", "", name)
    name = name.strip().strip(".")
    return name or fallback


def remote_size(url):
    """Total size of a URL via a 1-byte range request."""
    req = urllib.request.Request(
        url, headers=_headers({"Range": "bytes=0-0"})
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        content_range = resp.headers.get("Content-Range")
        if content_range and "/" in content_range:
            return int(content_range.split("/")[-1])
        length = resp.headers.get("Content-Length")
        return int(length) if length else 0


def download(url, dest, on_progress=None, should_cancel=None, chunk_size=1 << 16):
    """Download url to dest with resume support.

    Returns one of 'done', 'skipped'. on_progress(downloaded, total) is called
    periodically. should_cancel() is polled and raises Cancelled when true.
    """
    total = 0
    try:
        total = remote_size(url)
    except Exception:
        total = 0

    existing = os.path.getsize(dest) if os.path.exists(dest) else 0
    if total and existing == total:
        if on_progress:
            on_progress(existing, total)
        return "skipped"
    if total and existing > total:
        existing = 0
        with open(dest, "wb"):
            pass

    extra = {}
    if existing > 0:
        extra["Range"] = "bytes=%d-" % existing
    req = urllib.request.Request(url, headers=_headers(extra))
    resp = urllib.request.urlopen(req, timeout=120)

    resumed = existing > 0 and resp.status == 206
    if not resumed:
        existing = 0

    mode = "ab" if resumed else "wb"
    done = existing
    last_emit = 0.0
    with open(dest, mode) as handle:
        while True:
            if should_cancel and should_cancel():
                raise Cancelled()
            buf = resp.read(chunk_size)
            if not buf:
                break
            handle.write(buf)
            done += len(buf)
            now = time.time()
            if on_progress and (now - last_emit > 0.2 or (total and done >= total)):
                on_progress(done, total)
                last_emit = now
    resp.close()

    if on_progress:
        on_progress(done, total)
    return "done"

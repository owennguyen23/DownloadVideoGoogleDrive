#!/bin/sh
# Fetch — bấm đúp vào file này để chạy.
# macOS: nếu bấm đúp không chạy, hãy chuột phải > Open ở lần đầu tiên.

cd "$(dirname "$0")" || exit 1

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
fi

if [ -z "$PY" ]; then
  echo ""
  echo "  Chưa tìm thấy Python 3 trên máy này."
  echo ""
  echo "  Cách làm:"
  echo "    1. Mở https://www.python.org/downloads/"
  echo "    2. Tải và cài Python 3"
  echo "    3. Bấm đúp lại file này"
  echo ""
  echo "  Nhấn Enter để đóng."
  read -r _
  exit 1
fi

"$PY" server.py
status=$?

if [ "$status" -ne 0 ]; then
  echo ""
  echo "  Tool đã dừng do lỗi. Xem nội dung phía trên."
  echo "  Nhấn Enter để đóng."
  read -r _
fi

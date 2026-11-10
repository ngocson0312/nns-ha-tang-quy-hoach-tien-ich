#!/bin/bash
# macOS: bấm đúp file này để cài skill (lần đầu: chuột phải → Open nếu máy chặn)
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo " Chưa có Python 3. Tải tại https://www.python.org/downloads/ rồi bấm đúp lại file này."
  echo ""
  read -n 1 -s -r -p "Bấm phím bất kỳ để đóng…"
  exit 1
fi
python3 scripts/cai_dat.py "$@"
echo ""
read -n 1 -s -r -p "Bấm phím bất kỳ để đóng…"

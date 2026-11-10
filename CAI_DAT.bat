@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Ưu tiên "python" (đúng bản Claude Code sẽ gọi); "python" giả của Microsoft Store không chạy được nên phải thử thật
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
  py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
  if defined PY (
    echo  Lưu ý: lệnh "python" chưa có trong PATH - Claude Code có thể không gọi được Python.
    echo  Nên cài lại Python và tick ô "Add python.exe to PATH".
    echo.
  )
)
if not defined PY (
  echo.
  echo  Chưa có Python. Tải tại https://www.python.org/downloads/
  echo  Lúc cài nhớ tick ô "Add python.exe to PATH", cài xong bấm đúp lại file này.
  echo.
  pause
  exit /b 1
)
%PY% scripts\cai_dat.py %*
echo.
pause

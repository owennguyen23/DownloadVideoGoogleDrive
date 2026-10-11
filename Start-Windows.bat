@echo off
rem Fetch - double-click this file to start.
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"

if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)

if not defined PY (
  echo.
  echo   Khong tim thay Python 3 tren may nay.
  echo.
  echo   Cach lam:
  echo     1. Mo https://www.python.org/downloads/
  echo     2. Tai va cai Python 3, nho tich "Add Python to PATH"
  echo     3. Bam dup lai file nay
  echo.
  pause
  exit /b 1
)

%PY% server.py
if errorlevel 1 (
  echo.
  echo   Tool da dung do loi. Xem noi dung phia tren.
  echo.
  pause
)

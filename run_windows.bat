@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先双击setup_windows.bat完成安装。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 pause

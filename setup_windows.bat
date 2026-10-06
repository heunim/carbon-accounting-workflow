@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.12 --version
if errorlevel 1 (
  echo 请先安装Python 3.12并包含Python Launcher。
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo 依赖安装未成功，请检查网络后重新执行。
  pause
  exit /b 1
)
echo 安装完成。双击run_windows.bat启动演示。
pause

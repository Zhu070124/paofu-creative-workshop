@echo off
cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   🏭 泡芙的创意工坊                           ║
echo ║  Puff × Hermes × Claude Code               ║
echo ╚══════════════════════════════════════════════╝
echo.

REM 检查 Memory Hub
echo [1/2] 检查 Memory Hub...
curl -s http://127.0.0.1:8921/sources >nul 2>&1
if errorlevel 1 (
    echo [!] Memory Hub 未启动，正在启动...
    start "Memory Hub" python "%USERPROFILE%\..\..\..\D:\Users\DELL\clawd\memory-hub\hub.py" serve 8921
    timeout /t 3 /nobreak >nul
) else (
    echo [✓] Memory Hub 已在线
)

REM 检查 Puff
echo [2/2] 检查 Puff...
curl -s http://127.0.0.1:8920/ >nul 2>&1
if errorlevel 1 (
    echo [!] Puff 未启动，正在启动...
    start "Puff" python "D:\Users\DELL\clawd\puff\puff.py" serve 8920
    timeout /t 3 /nobreak >nul
) else (
    echo [✓] Puff 已在线
)

echo.
echo [✓] 启动工坊服务器...
start msedge --app="http://127.0.0.1:8922" --window-size=1200,800
python server.py 8922
pause

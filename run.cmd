@echo off
cd /d "%~dp0"
echo.
echo ╔══════════════════════════════════════════════╗
echo ║   🏭 泡芙的创意工坊 v2                         ║
echo ║  Workshop Hub + 3 Agent Clients              ║
echo ╚══════════════════════════════════════════════╝
echo.

set HTTP_PORT=9822
set WS_PORT=9823
set WORKSHOP_WS=ws://127.0.0.1:%WS_PORT%/ws
set WORKSHOP_TOKEN=paofu-workshop-2026

echo [1/4] Starting Workshop Hub...
start "Workshop Hub" python server.py %HTTP_PORT% %WS_PORT%
timeout /t 3 /nobreak >nul

echo [2/4] Starting Puff Agent...
start "Puff Agent" python agent_client.py puff
timeout /t 1 /nobreak >nul

echo [3/4] Starting Hermes Agent...
start "Hermes Agent" python agent_client.py hermes
timeout /t 1 /nobreak >nul

echo [4/4] Starting Claude Agent...
start "Claude Agent" python agent_client.py claude
timeout /t 2 /nobreak >nul

echo.
echo [OK] All systems ready!
echo   Dashboard: http://127.0.0.1:%HTTP_PORT%
echo.
start msedge --app="http://127.0.0.1:%HTTP_PORT%" --window-size=1200,800

pause

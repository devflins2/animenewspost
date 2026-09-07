@echo off
title AniReport Studio - Web Dashboard
cd /d "%~dp0"
echo ============================================================
echo Starting AniReport Studio Web Dashboard...
echo ============================================================
echo Opening http://localhost:5000 in default browser...
start http://localhost:5000
python server.py 5000
pause

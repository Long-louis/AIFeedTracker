@echo off
REM Simple background run script (for temporary testing)
echo Starting AI Video Robot in background...
echo.
echo NOTE: For production, please use install_service.bat to register as Windows service
echo       This script is mainly for development and testing
echo.

cd /d E:\ai_video_robot

REM Use start command to run in new minimized window
start /min "AI Video Robot" uv run python main.py --mode service

echo Program started in background!
echo.
echo To stop the program:
echo   - Kill python.exe process in Task Manager
echo   - Or close the "AI Video Robot" window
echo.

pause
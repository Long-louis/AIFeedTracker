@echo off
REM Quick service restart script for code updates
echo Restarting AI Video Robot Service...
echo.

set SERVICE_NAME=AIVideoRobot

REM Stop service
echo Stopping service...
net stop %SERVICE_NAME%
echo.

REM Start service
echo Starting service...
net start %SERVICE_NAME%
echo.

if %errorlevel% equ 0 (
    echo Service restarted successfully!
    echo Check logs in: log\service_stdout.log and log\app.log
) else (
    echo Failed to restart service!
    echo Check error details above.
)

echo.
pause

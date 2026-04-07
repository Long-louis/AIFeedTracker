@echo off
REM AI Video Robot Service Uninstallation Script
echo Uninstalling AI Video Robot Service...
echo.

set SERVICE_NAME=AIVideoRobot
set NSSM_PATH=D:\nssm-2.24-101-g897c7ad\win64\nssm.exe

REM Stop service
echo Stopping service...
net stop %SERVICE_NAME%
echo.

REM Remove service
echo Removing service...
"%NSSM_PATH%" remove %SERVICE_NAME% confirm
echo.

echo Service uninstalled successfully!
pause
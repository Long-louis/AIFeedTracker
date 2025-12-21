@echo off
REM AI Video Robot Service Installation Script
echo Installing AI Video Robot Service...

REM Set variables
set SERVICE_NAME=AIVideoRobot
set PROJECT_PATH=E:\ai_video_robot
set PYTHON_CMD=%PROJECT_PATH%\.venv\Scripts\python.exe
set SCRIPT_PATH=%PROJECT_PATH%\main.py

REM NSSM tool path
set NSSM_PATH=D:\nssm-2.24-101-g897c7ad\win64\nssm.exe

REM Install service
"%NSSM_PATH%" install %SERVICE_NAME% %PYTHON_CMD% %SCRIPT_PATH% --mode service

REM Set service parameters
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory %PROJECT_PATH%
"%NSSM_PATH%" set %SERVICE_NAME% DisplayName "AI Video Robot Monitor Service"
"%NSSM_PATH%" set %SERVICE_NAME% Description "Auto monitor Bilibili creators and push updates to Feishu"

REM Set startup type to auto
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Set log files
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout %PROJECT_PATH%\log\service_stdout.log
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr %PROJECT_PATH%\log\service_stderr.log

REM Set restart on failure
"%NSSM_PATH%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_PATH%" set %SERVICE_NAME% AppRestartDelay 30000

echo Service installation completed!
echo.
echo Manage service with following commands:
echo   Start service: net start %SERVICE_NAME%
echo   Stop service:  net stop %SERVICE_NAME%
echo   Uninstall:     "%NSSM_PATH%" remove %SERVICE_NAME% confirm
pause
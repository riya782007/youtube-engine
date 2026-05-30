@echo off
REM Wrapper that the Windows Task Scheduler invokes at 11:00 daily.
REM Keeping this tiny avoids the schtasks 261-character /TR limit.
REM Logs go to scripts\logs\daily_agent_<YYYY-MM-DD>.log

setlocal
set "PYTHON_EXE=C:\Users\Riya yadav\AppData\Local\Programs\Python\Python312\python.exe"
cd /d "%~dp0\.."
if not exist "scripts\logs" mkdir "scripts\logs"

REM Build a date-stamped log filename in YYYY-MM-DD form using PowerShell so
REM it works regardless of the user's regional date format.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i

set LOGFILE=scripts\logs\daily_agent_%TODAY%.log

echo. >> "%LOGFILE%"
echo ====== Daily run %DATE% %TIME% ====== >> "%LOGFILE%"
echo Working Directory: %CD% >> "%LOGFILE%"
echo Python Path: %PYTHON_EXE% >> "%LOGFILE%"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" scripts\daily_agent.py >> "%LOGFILE%" 2>&1
) else (
    echo ERROR: Python not found at %PYTHON_EXE% >> "%LOGFILE%"
    python scripts\daily_agent.py >> "%LOGFILE%" 2>&1
)
endlocal

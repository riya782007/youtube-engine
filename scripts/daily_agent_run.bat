@echo off
REM Wrapper that the Windows Task Scheduler invokes at 11:00 daily.
REM Keeping this tiny avoids the schtasks 261-character /TR limit.
REM Logs go to scripts\logs\daily_agent_<YYYY-MM-DD>.log

setlocal
cd /d "%~dp0\.."
if not exist "scripts\logs" mkdir "scripts\logs"

REM Build a date-stamped log filename in YYYY-MM-DD form using PowerShell so
REM it works regardless of the user's regional date format.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i

set LOGFILE=scripts\logs\daily_agent_%TODAY%.log

echo. >> "%LOGFILE%"
echo ====== Daily run %DATE% %TIME% ====== >> "%LOGFILE%"
python scripts\daily_agent.py >> "%LOGFILE%" 2>&1
endlocal

@echo off
cd /d "%~dp0.."
set "OUT=scripts\browser_diag.txt"
echo ===== render --help ===== > "%OUT%"
call npx --yes hyperframes render --help >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ===== hyperframes browser path ===== >> "%OUT%"
call npx --yes hyperframes browser path >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ===== TREE of .cache\hyperframes\chrome ===== >> "%OUT%"
dir /s /b "%USERPROFILE%\.cache\hyperframes\chrome" >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ===== DONE =====
echo wrote %OUT%
pause

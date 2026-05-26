@echo off
setlocal
set "ZIP=%USERPROFILE%\.cache\hyperframes\chrome\chrome-headless-shell\131.0.6778.85-chrome-headless-shell-win64.zip"
set "DEST=%USERPROFILE%\.cache\hyperframes\chrome\chrome-headless-shell\win64-131.0.6778.85"
set "OUT=%~dp0extract_check.txt"
echo ZIP=%ZIP%> "%OUT%"
echo DEST=%DEST%>> "%OUT%"
echo ===== zip exists? =====>> "%OUT%"
if exist "%ZIP%" (echo ZIP FOUND>> "%OUT%") else (echo ZIP MISSING>> "%OUT%")
echo ===== extracting =====>> "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -Force -LiteralPath '%ZIP%' -DestinationPath '%DEST%'; 'expand ok' } catch { $_.Exception.Message }" >> "%OUT%" 2>&1
echo ===== tree of DEST =====>> "%OUT%"
dir /s /b "%DEST%" >> "%OUT%" 2>&1
echo ===== exe check =====>> "%OUT%"
if exist "%DEST%\chrome-headless-shell-win64\chrome-headless-shell.exe" (echo EXE_OK>> "%OUT%") else (echo EXE_MISSING>> "%OUT%")
echo done. wrote %OUT%
pause

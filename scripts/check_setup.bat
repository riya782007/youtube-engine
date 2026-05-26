@echo off
REM Double-click this to check your PC setup for the YouTube Engine pipeline.
REM It runs check_setup.ps1 from the project root and writes setup_report.txt.
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_setup.ps1"
echo.
echo ---- check complete. Report saved as setup_report.txt ----
pause

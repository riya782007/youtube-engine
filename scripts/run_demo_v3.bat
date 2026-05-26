@echo off
REM ============================================================
REM  run_demo_v3.bat - build ONE demo Short with the v3 engine
REM  (real Pexels B-roll + faster motion + -14 LUFS audio).
REM
REM  Usage:  double-click for AI Tadka, OR from a terminal:
REM     scripts\run_demo_v3.bat ai-tadka
REM     scripts\run_demo_v3.bat paisa-pathshala
REM     scripts\run_demo_v3.bat dhandha-dimaag
REM ============================================================
setlocal
cd /d "%~dp0.."

set CH=%1
if "%CH%"=="" set CH=ai-tadka

echo.
echo === Building v3 demo for channel: %CH% ===
echo (Sarvam voice + Pexels stock footage + hyperframes render)
echo.

python scripts\make_video.py --job "channels\%CH%\jobs\example.json"
if errorlevel 1 (
  echo.
  echo Build FAILED - scroll up for the error.
  pause
  exit /b 1
)

echo.
echo === Done. Opening the newest render folder... ===
for /f "delims=" %%D in ('dir /b /ad /o-d "channels\%CH%\renders"') do (
  start "" "channels\%CH%\renders\%%D"
  goto :done
)
:done
echo Look for output.mp4 in the folder that just opened.
pause

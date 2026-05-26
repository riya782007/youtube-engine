@echo off
REM Downloads the hyperframes browser (correct command: 'browser ensure'),
REM then rebuilds + renders the AI Tadka demo.
cd /d "%~dp0.."
echo Step 1: ensuring the hyperframes headless browser is downloaded (one-time, ~150 MB)...
call npx --yes hyperframes browser ensure
echo.
echo Step 2: rebuilding + rendering the demo...
python scripts\make_video.py --job channels\ai-tadka\jobs\example.json
echo.
echo ---- finished. Look in channels\ai-tadka\renders\ for output.mp4 ----
pause

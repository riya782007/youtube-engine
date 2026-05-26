@echo off
REM Builds one demo Short (AI Tadka example job) end-to-end.
cd /d "%~dp0.."
echo Building demo video for AI Tadka...
echo The FIRST render downloads hyperframes + a headless browser, so it may take
echo a few minutes. Later renders are much faster.
echo.
python scripts\make_video.py --job channels\ai-tadka\jobs\example.json
echo.
echo ---- finished. The MP4 is in channels\ai-tadka\renders\ ----
pause

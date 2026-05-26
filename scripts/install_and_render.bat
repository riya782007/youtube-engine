@echo off
REM One-time: download hyperframes' headless browser, then render the demo
REM that was already built (reuses its voice.wav, so no new API call).
cd /d "%~dp0.."
echo Step 1: installing hyperframes headless browser (one-time, ~150 MB)...
call npx --yes hyperframes browser --install
echo.
echo Step 2: rendering the existing demo composition...
cd "channels\ai-tadka\renders\chatgpt-se-2-minute-me-professional-resume-20260523-120906"
call npx --yes hyperframes render --output output.mp4
echo.
echo ---- finished. Look for output.mp4 in this folder. ----
pause

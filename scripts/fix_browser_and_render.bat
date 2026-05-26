@echo off
REM Works around a hyperframes 0.6.38 path mismatch: 'browser ensure' downloads
REM chrome-headless-shell to one folder, but the renderer looks in another.
REM We mirror the downloaded browser to the path the renderer expects, then render.
setlocal
set "SRC=%USERPROFILE%\.cache\hyperframes\chrome\chrome-headless-shell\win64-131.0.6778.85\chrome-headless-shell-win64"
set "DST=%USERPROFILE%\.cache\hyperframes\chrome\chrome-headless-shell-win64-131.0.6778.85\chrome-headless-shell-win64"
echo Mirroring browser:
echo   from %SRC%
echo   to   %DST%
robocopy "%SRC%" "%DST%" /E /NFL /NDL /NJH /NJS /NC /NS
echo robocopy exit code: %ERRORLEVEL%  (0-7 = success)
echo.
cd /d "%~dp0.."
echo Rendering the demo...
python scripts\make_video.py --job channels\ai-tadka\jobs\example.json
echo.
echo ---- finished. Look in channels\ai-tadka\renders\ for output.mp4 ----
pause

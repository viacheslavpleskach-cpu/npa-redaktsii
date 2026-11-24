@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Povne onovlennia arkhivu npa-redaktsii cherez API (Downloads\npa-arkhiv; ~20-40 khv.)
python full_sync.py > ..\full_sync_console.txt 2>&1
>> ..\full_sync_console.txt echo exit=%errorlevel%
type ..\full_sync_console.txt
echo.
echo Gotovo. Rezultaty: Downloads\out_v41\full
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Korotka zhyva perevirka sync_api v4.1.5 z avtoperevirkoiu umov (kopiia kopiia_v41; ~5-25 khv.)
python live_v415.py > ..\..\..\live_v415_console.txt 2>&1
>> ..\..\..\live_v415_console.txt echo exit=%errorlevel%
type ..\..\..\live_v415_console.txt
echo.
echo Gotovo. Rezultaty: Downloads\out_v41\v415
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Zhyva perevirka v4.1.7 i vypravlennia 2343-12 (kopiia kopiia_v417; ~5-10 khv.)
python live_v417.py > ..\live_v417_console.txt 2>&1
>> ..\live_v417_console.txt echo exit=%errorlevel%
type ..\live_v417_console.txt
echo.
echo Gotovo. Rezultaty: Downloads\out_v41\v417
pause

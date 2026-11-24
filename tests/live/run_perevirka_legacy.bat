@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Perevirka starykh tekstiv cherez API (porciia v mezhakh 150 MiB na dobu; ~30-60 khv.)
python perevirka_legacy.py > perevirka_legacy_console.txt 2>&1
>> perevirka_legacy_console.txt echo exit=%errorlevel%
type perevirka_legacy_console.txt
echo.
pause

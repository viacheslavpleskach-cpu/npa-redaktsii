@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Zhyvi perevirky sync_api v4.1 (lyshe kopiia arkhivu kopiia_v41; ~20-40 khv.)
python live_v41.py "%~1" > ..\..\..\live_v41_console.txt 2>&1
>> ..\..\..\live_v41_console.txt echo exit=%errorlevel%
type ..\..\..\live_v41_console.txt
echo.
echo Gotovo. Prykripit u chat fail rezultaty_v41.zip (lezhyt poruch iz tekoiu npa_api_v4_1_candidate).
pause

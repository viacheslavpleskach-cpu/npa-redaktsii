@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if not exist "..\..\out_v41" mkdir "..\..\out_v41"
echo Oflain-testy v4.1.6 (bez merezhi, ~10 s)
(python --version & python -c "import platform;print(platform.platform())" & python -m unittest discover -s . -p "test_*.py" -v) > "..\..\out_v41\offline_tests_v4_1_6_windows.txt" 2>&1
>> "..\..\out_v41\offline_tests_v4_1_6_windows.txt" echo exit=%errorlevel%
type "..\..\out_v41\offline_tests_v4_1_6_windows.txt" | findstr /b /c:"Ran " /c:"OK" /c:"FAILED" /c:"exit="
echo.
echo Gotovo. Rezultat: Downloads\out_v41\offline_tests_v4_1_6_windows.txt
pause

@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d %~dp0

rem ============================================================
rem  Bumao XTGL console launcher - ONE byte-identical copy for all
rem  three editions. Pure ASCII on purpose: cmd parses a .bat with
rem  the console code page inherited at launch time, so any non-ASCII
rem  byte parses differently under cp936 vs cp65001 and can break the
rem  file. Chinese text is printed by serve.py via WriteConsoleW.
rem
rem  PYTHONUTF8=1 and PYTHONIOENCODING=utf-8 are set before any
rem  interpreter runs, so a console under cp936 still gets UTF-8 I/O.
rem
rem  The port is NOT hardcoded here. serve.py reads it from
rem  web_config.json and walks up to 40 ports if it is taken, then
rem  prints the real URL and opens the browser itself.
rem
rem  Interpreter probing order (first working candidate wins):
rem    1) py -3
rem    2) python3
rem    3) python
rem    4) python_path.txt in this folder (local override, one path)
rem  Every candidate is executed with "-c import sys", so the Windows
rem  Store stub (which exits 9009) is rejected instead of being used.
rem ============================================================

set "PYEXE="
set "PYARG="

rem 1) py -3 launcher
if not defined PYEXE (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    set "PYEXE=py"
    set "PYARG=-3"
  )
)

rem 2) python3
if not defined PYEXE (
  python3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PYEXE=python3"
)

rem 3) python
if not defined PYEXE (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)

rem 4) local override: python_path.txt, one interpreter path per line (last resort)
if not defined PYEXE if exist "%~dp0python_path.txt" (
  for /f "usebackq delims=" %%L in ("%~dp0python_path.txt") do (
    if not defined PYEXE (
      "%%~L" -c "import sys" >nul 2>&1
      if not errorlevel 1 set "PYEXE=%%~L"
    )
  )
)

if not defined PYEXE (
  echo [Bumao XTGL] No usable Python 3 found.
  echo   Tried: py -3, python3, python, python_path.txt.
  echo   Put the full path of python.exe into python_path.txt in this folder.
  pause
  exit /b 1
)

echo [Bumao XTGL] Starting console...
echo Interpreter: %PYEXE% %PYARG%
echo Port comes from web_config.json; serve.py prints the URL and opens the browser.
echo Close this window to stop the service.
echo.
"%PYEXE%" %PYARG% serve.py
echo.
echo [Bumao XTGL] serve.py exited with code %errorlevel%.
pause

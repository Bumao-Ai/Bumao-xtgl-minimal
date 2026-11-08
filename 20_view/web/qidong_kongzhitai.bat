@echo off
chcp 65001 >nul
cd /d %~dp0

rem ============================================================
rem  Bumao XTGL console launcher - ONE byte-identical copy for all
rem  three editions. This file is pure ASCII on purpose: cmd parses
rem  a .bat with the console code page inherited at launch time, so
rem  any non-ASCII byte here parses differently under cp936 vs cp65001
rem  and can break the file. Chinese text is printed by serve.py
rem  instead (Python writes the console via WriteConsoleW, which is
rem  Unicode-native and code-page independent).
rem
rem  The port is NOT hardcoded here. serve.py reads it from
rem  web_config.json and walks up to 40 ports if it is taken, then
rem  prints the real URL and opens the browser itself.
rem  History: the old launcher hardcoded PORT and polled that port.
rem  One edition shipped bat=8801 while web_config.json said 8802, so
rem  the server came up fine and the launcher still always reported
rem  "startup failed". Removing the hardcoded port removes the whole
rem  class of drift instead of adding a check for it.
rem ============================================================

rem ---- Find a real Python: "python" on PATH may be the Store stub ----
set "PY="
python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
  ) do if not defined PY if exist "%%~P" set "PY=%%~P"
)
if not defined PY (
  echo [Bumao XTGL] No usable Python found.
  echo Install Python 3.8+ and tick "Add Python to PATH", then retry.
  pause
  exit /b 1
)

echo [Bumao XTGL] Starting console...
echo Interpreter: %PY%
echo Port comes from web_config.json; serve.py prints the URL and opens the browser.
echo Close this window to stop the service.
echo.
"%PY%" serve.py
echo.
echo [Bumao XTGL] serve.py exited with code %errorlevel%.
pause

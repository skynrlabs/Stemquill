@echo off
cd /d "%~dp0"
rem Prefer Python 3.11 (needed for basic-pitch), otherwise use the default Python.
set PY=python
py -3.11 --version >nul 2>&1 && set PY=py -3.11
echo Using: %PY%
%PY% --version
echo Installing Stemquill libraries...
%PY% -m pip install -r requirements.txt
echo.
if not "%PY%"=="py -3.11" (
  echo basic-pitch skipped: it needs Python 3.11. The tool still works without it.
  echo To add it later: run "py install 3.11" in Command Prompt, then run this file again.
  goto done
)
choice /c YN /m "Install basic-pitch for better chord detection"
if errorlevel 2 goto done
%PY% -m pip install basic-pitch
:done
echo.
echo All set. Double-click "Start Stemquill.bat" to open the tool.
pause

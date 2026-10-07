@echo off
cd /d "%~dp0"
set PY=python
py -3.11 --version >nul 2>&1 && set PY=py -3.11
%PY% -m stemquill
if errorlevel 1 pause

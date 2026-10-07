@echo off
cd /d "%~dp0"
set PY=python
py -3.11 --version >nul 2>&1 && set PY=py -3.11
%PY% stemquill.py
if errorlevel 1 pause

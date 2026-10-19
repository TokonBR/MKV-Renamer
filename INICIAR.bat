@echo off
cd /d "%~dp0"
py -3 Scene_Renamer.py
if errorlevel 1 pause

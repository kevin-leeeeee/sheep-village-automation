@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" pythonw upgrade_and_attack.py
exit

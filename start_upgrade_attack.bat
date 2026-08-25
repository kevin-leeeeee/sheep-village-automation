@echo off
chcp 65001 >nul
cd /d "%~dp0"
python upgrade_and_attack.py
pause

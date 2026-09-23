@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" pythonw boss_auto_clicker.py
exit

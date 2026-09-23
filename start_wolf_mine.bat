@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" pythonw wolf_mine_speedup.py
exit

@echo off
chcp 65001 >nul
cd /d "%~dp0"
python wolf_mine_speedup.py
pause

@echo off
echo Stopping background pythonw.exe processes...
taskkill /F /IM pythonw.exe
echo.
echo Process terminated.
pause

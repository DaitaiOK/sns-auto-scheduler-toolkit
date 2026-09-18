@echo off
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo Starting Unified Social Media Scheduler...
python unified_scheduler.py
pause

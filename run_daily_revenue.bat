@echo off
echo Starting daily revenue calculation...
cd /d "%~dp0"
python daily_revenue_calculator.py
echo Daily revenue calculation completed.
pause

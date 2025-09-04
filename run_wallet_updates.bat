@echo off
echo Starting operator wallet updates...
cd /d "%~dp0"
python update_operator_wallets.py
echo Operator wallet updates completed.
pause

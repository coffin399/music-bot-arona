@echo off
call .venv\Scripts\activate.bat

pip install -r requirements.txt
python bot.py

pause
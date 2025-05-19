@echo off
echo START ARONA
pip install -r requirements.txt
start java -jar Lavalink.jar
timeout /t 50 > nul
start python bot.py
pause
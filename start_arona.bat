@echo off
echo START ARONA
pip install -r requirements.txt
start java -jar Lavalink.jar
timeout /t 10 > nul
start python bot.py
pause
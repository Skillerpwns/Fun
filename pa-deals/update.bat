@echo off
rem Scan every store, then open the deals site.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m padeals scrape
python -m padeals serve

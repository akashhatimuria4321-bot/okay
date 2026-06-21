@echo off
cd /d "%~dp0"
echo Installing JARVIS OMEGA V9 dependencies...
python -m pip install -r requirements.txt
echo.
echo Installation complete! Copy .env.example to .env and add your API keys.
pause

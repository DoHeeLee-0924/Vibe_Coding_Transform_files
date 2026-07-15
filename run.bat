@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo            FILE CONVERTER
echo ==========================================
echo.
echo  Starting the local server...
echo  A browser window will open automatically in a moment.
echo.
echo  * Keep THIS black window open while you use the converter.
echo  * To quit: close this window (or press Ctrl+C here).
echo.

rem Check Python is available
where python >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Python was not found on this PC.
    echo          Please install Python first ^(https://www.python.org^).
    echo.
    pause
    exit /b
)

rem Open the browser 2 seconds later, in the background,
rem so the server has time to start first.
start "" /b powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"

rem Start the web server (this keeps running until the window is closed)
python "%~dp0app.py"

rem If the server stops for any reason, keep the window open to show why.
echo.
echo  The server has stopped.
pause

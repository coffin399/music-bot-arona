@echo off
REM バッチファイルがあるディレクトリをカレントディレクトリにする
cd /d "%~dp0"

REM ----- Lavalinkサーバーの設定 -----
set LAVALINK_JAR_PATH=lavalink\Lavalink.jar
set JAVA_OPTS=-Xmx1024m -Xms128m

REM ----- Python BOTの設定 -----
set PYTHON_SCRIPT_PATH=main.py
set REQUIREMENTS_FILE=requirements.txt
REM Pythonの仮想環境を使用している場合は、activateスクリプトのパスを指定
REM 例: set VENV_ACTIVATE_PATH=venv\Scripts\activate.bat

echo =====================================
echo  Lavalink Music Bot ARONA Launcher
echo =====================================
echo.

REM Python仮想環境のアクティベート (コメントアウトを解除してパスを修正)
REM IF EXIST "%VENV_ACTIVATE_PATH%" (
REM     echo Activating Python virtual environment...
REM     call "%VENV_ACTIVATE_PATH%"
REM     echo Virtual environment activated.
REM ) ELSE (
REM     echo Python virtual environment not found or not specified.
REM     echo Running with system Python or globally installed packages.
REM )
REM echo.

REM 必要なPythonライブラリのインストール/アップデート
IF EXIST "%REQUIREMENTS_FILE%" (
    echo Checking and installing/updating Python libraries from %REQUIREMENTS_FILE%...
    python -m pip install -U -r "%REQUIREMENTS_FILE%"
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install/update Python libraries. Please check the errors above.
        pause
        exit /b %ERRORLEVEL%
    )
    echo Python libraries are up to date.
) ELSE (
    echo %REQUIREMENTS_FILE% not found. Skipping library installation.
    echo Please ensure all required Python libraries are installed manually.
)
echo.

REM Lavalinkサーバーをバックグラウンドで起動
echo Starting Lavalink server...
start "Lavalink Server" cmd /c "cd lavalink && java %JAVA_OPTS% -jar Lavalink.jar"
echo Lavalink server started in a new window. (Check that window for logs)
echo Waiting a few seconds for Lavalink to initialize...
timeout /t 10 /nobreak >nul
REM Lavalinkが起動するまで少し待機 (秒数は環境に合わせて調整)

echo.
REM Python BOTを起動
echo Starting Python Discord Bot...
python "%PYTHON_SCRIPT_PATH%"

echo.
echo Bot script has finished or was closed.
echo You may need to manually close the Lavalink Server window if it's still open.
pause
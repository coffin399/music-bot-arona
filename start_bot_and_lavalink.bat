@echo off
REM バッチファイルがあるディレクトリをカレントディレクトリにする
cd /d "%~dp0"

REM ----- Lavalinkサーバーの設定 -----
set LAVALINK_JAR_PATH=lavalink\Lavalink.jar
set LAVALINK_CONFIG_PATH=lavalink\application.yml
set JAVA_OPTS=-Xmx1024m -Xms128m

REM ----- Python BOTの設定 -----
set PYTHON_SCRIPT_PATH=main.py
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
REM ) ELSE (
REM     echo Python virtual environment not found or not specified. Running with system Python.
REM )
REM echo.

REM Lavalinkサーバーをバックグラウンドで起動
echo Starting Lavalink server...
REM start "Lavalink Server" java %JAVA_OPTS% -jar "%LAVALINK_JAR_PATH%"
REM ↑ startコマンドを使うと新しいウィンドウで起動し、バッチは続行します。
REM Lavalinkのログをコンソールに出したい場合や、起動確認をしたい場合は以下のようにします。
REM この場合、Lavalinkが終了するまで次のPython BOTは起動しません。
REM そのため、Lavalink起動後に手動でBOTを起動するか、Lavalinkを別ターミナルで起動する必要があります。

REM ここでは、Lavalinkを別ウィンドウで起動し、BOTの起動を続行する形にします。
REM Lavalinkのウィンドウを閉じるまでLavalinkは動作し続けます。
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
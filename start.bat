@echo off
rem MeloTab launcher: starts backend (:8000) + web (:5173) in minimized windows, then opens the browser.
rem Close the two "MeloTab ..." windows (or run with argument "stop") to shut everything down.
setlocal
cd /d "%~dp0"

if /i "%~1"=="stop" goto :stop

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] backend\.venv not found. Set up the Python environment first ^(see README.md^).
  pause & exit /b 1
)
if not exist "apps\web\node_modules" (
  echo [ERROR] apps\web\node_modules not found. Run: cd apps\web ^&^& npm install
  pause & exit /b 1
)

rem --- backend (skip if already running) ---
powershell -NoProfile -Command "try { (Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo Starting backend...
  start "MeloTab backend" /min /d "%~dp0backend" ".venv\Scripts\python.exe" -m uvicorn melotab.api.app:app --port 8000 --log-level warning
) else (
  echo Backend already running.
)

rem --- web (skip if already running) ---
powershell -NoProfile -Command "try { (Invoke-WebRequest http://localhost:5173 -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo Starting web...
  start "MeloTab web" /min /d "%~dp0apps\web" cmd /c npm run dev -- --port 5173 --strictPort
) else (
  echo Web already running.
)

rem --- wait for both, then open the browser ---
echo Waiting for servers...
powershell -NoProfile -Command "for ($i=0; $i -lt 60; $i++) { try { $a=(Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing -TimeoutSec 2).StatusCode; $b=(Invoke-WebRequest http://localhost:5173 -UseBasicParsing -TimeoutSec 2).StatusCode; if ($a -eq 200 -and $b -eq 200) { exit 0 } } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
  echo [ERROR] Servers did not start within 30 s. Check the minimized "MeloTab ..." windows.
  pause & exit /b 1
)
echo Opening http://localhost:5173
start "" "http://localhost:5173"
exit /b 0

:stop
echo Stopping MeloTab...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*melotab.api.app*') -or ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*vite*5173*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Done.
exit /b 0

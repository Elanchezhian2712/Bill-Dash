@echo off
REM Build and start Bill-Dash (Postgres + Django + nginx) in the background.
REM App: http://localhost:8080
REM Retries the build - pip downloads time out on slow connections, and
REM Docker keeps the layers that already succeeded, so a retry picks up
REM where the last attempt stopped.

setlocal
set ATTEMPTS=3
set COUNT=0

:build
set /a COUNT+=1
echo Starting Bill-Dash (attempt %COUNT% of %ATTEMPTS%)...
docker compose up --build -d
if not errorlevel 1 goto started

if %COUNT% lss %ATTEMPTS% (
    echo.
    echo Build failed - retrying. Layers already built are reused.
    goto build
)

echo.
echo Failed to start after %ATTEMPTS% attempts.
echo   - Is Docker Desktop running? Look for "Engine running" in its window.
echo   - If the error mentions a pip read timeout, your connection is slow;
echo     just run this again, each attempt gets further.
exit /b 1

:started
echo.
echo Bill-Dash is starting at http://localhost:8080
echo Follow the logs with: docker-logs.cmd
echo Create the admin user with: docker-createuser.cmd

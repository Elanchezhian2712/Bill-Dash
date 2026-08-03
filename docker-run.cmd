@echo off
REM Build and start Bill-Dash (Postgres + Django + nginx) in the background.
REM App: http://localhost:8080

docker compose up --build -d
if errorlevel 1 (
    echo.
    echo Failed to start. Is Docker Desktop running?
    exit /b 1
)

echo.
echo Bill-Dash is starting at http://localhost:8080
echo Follow the logs with: docker-logs.cmd

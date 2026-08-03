@echo off
REM Stop and remove the containers.
REM   docker-remove.cmd         -> keeps the database (data survives)
REM   docker-remove.cmd --all   -> ALSO DELETES the database volume permanently

if "%~1"=="--all" goto removeall

docker compose down
echo Containers removed. Database volume kept - use --all to delete it too.
goto :eof

:removeall
echo WARNING: this deletes the Postgres volume - all invoices and users will be lost.
set /p confirm="Type 'yes' to continue: "
if /i not "%confirm%"=="yes" (
    echo Aborted.
    exit /b 1
)
docker compose down -v
echo Containers and database volume removed.

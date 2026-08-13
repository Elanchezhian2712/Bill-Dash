@echo off
REM Run migrations inside the running web container.
REM Run this to apply database changes after pulling new migrations.

echo Running migrations...
docker compose exec web python manage.py migrate

if errorlevel 1 (
    echo.
    echo Migration failed. Make sure the app is running.
    exit /b 1
)

echo.
echo Migrations applied successfully!

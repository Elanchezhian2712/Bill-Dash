@echo off
REM Generate new migrations inside the running web container.
REM Run this after modifying your Django models.

echo Generating new migrations...
docker compose exec web python manage.py makemigrations

if errorlevel 1 (
    echo.
    echo Make migrations failed. Make sure the app is running.
    exit /b 1
)

echo.
echo Migrations generated successfully! (Remember to commit the new files to git)

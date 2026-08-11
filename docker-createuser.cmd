@echo off
REM Create the admin user inside the running web container.
REM Run this once after docker-run.cmd has started the app.
REM Edit the values below to change the credentials.

set DJANGO_SUPERUSER_USERNAME=KavinText
set DJANGO_SUPERUSER_EMAIL=admin@example.com
set DJANGO_SUPERUSER_PASSWORD=Admin@123#

docker compose exec ^
    -e DJANGO_SUPERUSER_USERNAME=%DJANGO_SUPERUSER_USERNAME% ^
    -e DJANGO_SUPERUSER_EMAIL=%DJANGO_SUPERUSER_EMAIL% ^
    -e DJANGO_SUPERUSER_PASSWORD=%DJANGO_SUPERUSER_PASSWORD% ^
    web python manage.py createsuperuser --noinput

if errorlevel 1 (
    echo.
    echo Could not create the user. It may already exist, or the app is not running.
    exit /b 1
)

echo.
echo Admin user '%DJANGO_SUPERUSER_USERNAME%' created.

@echo off
REM Follow container logs.
REM   docker-logs.cmd        -> all services
REM   docker-logs.cmd web    -> Django only (nginx / db also valid)

docker compose logs -f --tail=100 %*

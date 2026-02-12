@echo off
echo Starting Freqtrade Algorithmic Trading Bot...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker Compose is not available. Please install Docker Compose.
    pause
    exit /b 1
)

echo Docker is running. Starting services...
echo.

REM Create necessary directories if they don't exist
if not exist "user_data" mkdir user_data
if not exist "user_data\strategies" mkdir user_data\strategies
if not exist "user_data\data" mkdir user_data\data
if not exist "user_data\logs" mkdir user_data\logs
if not exist "config" mkdir config
if not exist "logs" mkdir logs

echo Directories created/verified.
echo.

REM Start the services
echo Starting Freqtrade services...
docker-compose up -d

if %errorlevel% equ 0 (
    echo.
    echo Services started successfully!
    echo.
    echo Access points:
    echo - Freqtrade API/WebUI: http://localhost:8080
    echo - Log download API:   http://localhost:8081/api/v1/logs/download
    echo.
    echo To view logs: docker-compose logs -f
    echo To stop services: docker-compose down
    echo.
) else (
    echo.
    echo Error starting services. Check Docker logs for details.
    echo.
)

pause




#!/bin/bash

echo "Starting Freqtrade Algorithmic Trading Bot..."
echo

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    echo "On WSL2, you may need to start Docker Desktop on Windows."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

echo "Docker is running. Starting services..."
echo

# Create necessary directories if they don't exist
mkdir -p user_data/strategies
mkdir -p user_data/data
mkdir -p user_data/logs
mkdir -p config
mkdir -p logs

echo "Directories created/verified."
echo

# Start the services
echo "Starting Freqtrade services..."
docker-compose up -d

if [ $? -eq 0 ]; then
    echo
    echo "Services started successfully!"
    echo
    echo "Access points:"
    echo "- Freqtrade API/WebUI: http://localhost:8080"
    echo "- Log download API:   http://localhost:8081/api/v1/logs/download"
    echo
    echo "To view logs: docker-compose logs -f"
    echo "To stop services: docker-compose down"
    echo
else
    echo
    echo "Error starting services. Check Docker logs for details."
    echo
fi




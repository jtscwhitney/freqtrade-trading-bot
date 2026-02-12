#!/bin/bash
# Deploy or update Freqtrade on Digital Ocean Droplet
# Run from project root: ./deploy/deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=== Freqtrade Deploy ==="

# Ensure directories exist
mkdir -p user_data/strategies user_data/data user_data/logs config

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo "Loaded .env"
fi

# Build and start
docker compose build --no-cache
docker compose up -d

echo ""
echo "=== Deploy complete ==="
echo "Services:"
echo "  - Freqtrade API:  http://$(hostname -I | awk '{print $1}'):8080"
echo "  - Log download:   http://$(hostname -I | awk '{print $1}'):8081/api/v1/logs/download"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop:      docker compose down"
echo ""

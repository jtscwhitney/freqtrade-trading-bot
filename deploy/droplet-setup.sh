#!/bin/bash
# One-time Digital Ocean Droplet setup for Freqtrade
# Run as root or with sudo on a fresh Ubuntu 22.04 droplet

set -e

echo "=== Freqtrade Droplet Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable Docker to start on boot
systemctl enable docker
systemctl start docker

# Optional: allow non-root user to run docker (add your deploy user)
# usermod -aG docker $USER

# Create app directory
mkdir -p /opt/freqtrade
chown -R $(whoami):$(whoami) /opt/freqtrade 2>/dev/null || true

# Firewall (optional - uncomment to enable)
# ufw allow 22
# ufw allow 8080
# ufw allow 8081
# ufw allow 5555
# ufw --force enable

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Clone your repo to /opt/freqtrade"
echo "  2. Copy deploy/.env.example to .env and set credentials"
echo "  3. Add exchange API keys to user_data/config_sniper_BTC_DryRun.json"
echo "  4. Run: ./deploy/deploy.sh"
echo ""

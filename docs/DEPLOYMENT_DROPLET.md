# Deploy Freqtrade to Digital Ocean Droplet

This guide walks through deploying the Freqtrade trading bot (with OracleSurfer strategy and Log API) to a Digital Ocean Droplet.

## Architecture

- **Freqtrade** (port 8080): Main trading bot, API, Web UI
- **Log API** (port 8081): Serves log file download at `/api/v1/logs/download`
- **ZMQ** (port 5555): Reserved for Regime Filter broadcasts (if used)

Both services share the `user_data` volume; the log API reads the same log file Freqtrade writes.

## Prerequisites

- Digital Ocean account
- SSH key for droplet access
- Git repository with this project

## Step 1: Create Droplet

1. Go to [Digital Ocean Droplets](https://cloud.digitalocean.com/droplets/new)
2. Choose **Ubuntu 22.04 LTS**
3. Plan: **Basic** ≥ 2 GB RAM (4 GB recommended for FreqAI)
4. Add your SSH key
5. Create droplet and note the IP address

## Step 2: One-Time Server Setup

SSH into your droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

Clone the repo and run the setup script:

```bash
git clone https://github.com/YOUR_USER/YOUR_REPO.git /opt/freqtrade
cd /opt/freqtrade
chmod +x deploy/droplet-setup.sh
./deploy/droplet-setup.sh
```

## Step 3: Configure Secrets

### 3a. API credentials

```bash
cd /opt/freqtrade
cp deploy/.env.example .env
nano .env   # Edit FREQTRADE_API_USERNAME and FREQTRADE_API_PASSWORD
```

### 3b. Exchange API keys

Edit `user_data/config_sniper_BTC_DryRun.json` and add your Binance API key and secret in the `exchange` section:

```json
"exchange": {
  "key": "your-binance-api-key",
  "secret": "your-binance-api-secret",
  ...
}
```

Do this only when moving from dry-run to live. Never commit these to git.

## Step 4: Deploy

```bash
cd /opt/freqtrade
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## Step 5: Verify

- **Freqtrade API**: `http://YOUR_DROPLET_IP:8080` (login with API credentials)
- **Log download**: `http://YOUR_DROPLET_IP:8081/api/v1/logs/download` (Basic Auth)
- **Health check**: `http://YOUR_DROPLET_IP:8081/api/v1/logs/health`

## Updating

From the project root:

```bash
git pull
./deploy/deploy.sh
```

## Security Notes

1. **Firewall**: Enable UFW and allow only ports 22, 8080, 8081 (and 5555 if needed)
2. **Secrets**: Use `.env` for credentials; ensure `.env` is in `.gitignore`
3. **HTTPS**: For production, put a reverse proxy (nginx) in front and use SSL

## Troubleshooting

| Issue | Check |
|-------|-------|
| Container won't start | `docker compose logs freqtrade` |
| Log download 404 | Log file may not exist yet; wait for Freqtrade to write logs |
| Out of memory | Upgrade droplet to 4 GB+ for FreqAI |
| Exchange errors | Verify API keys and IP whitelist on Binance |

# Browser Access Configuration for Oracle & OracleSurfer

## Current Issues Found

### ✅ Fixed Issues
1. **API Server Config Added**: `config_sniper_BTC_DryRun.json` now has API server configuration
2. **Port Mapping in docker-compose.yml**: Port 8080 is defined (but not used with `docker compose run`)

### ❌ Issues to Fix

#### Issue 1: Ports Not Mapped
**Problem**: When using `docker compose run --rm`, ports are NOT automatically mapped from docker-compose.yml.

**Current Container Status**: No ports exposed (PORTS column empty)

**Solution Options**:

**Option A: Use `--service-ports` flag** (Recommended)
```bash
docker compose run --rm --service-ports freqtrade trade \
  --config user_data/config_sniper_BTC_DryRun.json \
  --strategy OracleSurfer_v12_PROD \
  --freqaimodel XGBoostClassifier \
  --logfile /freqtrade/user_data/logs/freqtrade.log \
  -v
```

**Option B: Explicitly map ports**
```bash
docker compose run --rm -p 8080:8080 freqtrade trade \
  --config user_data/config_sniper_BTC_DryRun.json \
  --strategy OracleSurfer_v12_PROD \
  --freqaimodel XGBoostClassifier \
  --logfile /freqtrade/user_data/logs/freqtrade.log \
  -v
```

**Option C: Use `docker compose up`** (Best for persistent service)
Update `docker-compose.yml` command section to match your current setup, then:
```bash
docker compose up -d freqtrade
```

#### Issue 2: docker-compose.yml Command Mismatch
**Problem**: docker-compose.yml has hardcoded command that doesn't match your current setup.

**Current docker-compose.yml command**:
- Uses: `config_oracle.json`
- Uses: `RegimeValidation` strategy
- Uses: `tradesv3.sqlite` database

**Your current setup**:
- Uses: `config_sniper_BTC_DryRun.json`
- Uses: `OracleSurfer_v12_PROD` strategy
- Uses: Different database path

**Solution**: If you want to use `docker compose up`, update the command section in docker-compose.yml.

## Configuration Summary

### API Server Settings (Both Configs)

**config_sniper_BTC_DryRun.json**:
- Port: 8080
- Username: `freqtrader`
- Password: `SuperSecurePassword123`
- Enabled: ✅ Yes

**config_oracle.json**:
- Port: 8080
- Username: `freqtrader`
- Password: `SuperSecurePassword123`
- Enabled: ✅ Yes

### Port Mappings (docker-compose.yml)
- 8080:8080 - API/WebUI
- 5555:5555 - ZMQ

## Access Information

### Web UI Access
- **URL**: http://localhost:8080
- **Username**: `freqtrader`
- **Password**: `SuperSecurePassword123`

### What You'll See
- **The Oracle**: FreqAI model predictions (regime: BULL/BEAR/NEUTRAL)
- **OracleSurfer**: Strategy performance, trades, entry/exit signals
- **Real-time Monitoring**: Current trades, profit/loss, bot status

## Recommended Restart Command

For browser access with your current setup:

```bash
docker compose run --rm --service-ports freqtrade trade \
  --config user_data/config_sniper_BTC_DryRun.json \
  --strategy OracleSurfer_v12_PROD \
  --freqaimodel XGBoostClassifier \
  --logfile /freqtrade/user_data/logs/freqtrade.log \
  -v
```

**Key Addition**: `--service-ports` flag to expose port 8080

## Verification Steps

After restarting:

1. **Check Port Mapping**:
   ```bash
   docker ps --filter "name=freqtrade" --format "table {{.Names}}\t{{.Ports}}"
   ```
   Should show: `0.0.0.0:8080->8080/tcp`

2. **Test Browser Access**:
   - Open: http://localhost:8080
   - Login with credentials above
   - Should see Freqtrade web UI

3. **Check Logs for API Server**:
   ```bash
   docker logs <container_name> | grep -i "api\|server\|8080"
   ```
   Should show API server starting on port 8080

## Notes

- The API server starts automatically when `api_server.enabled: true` is in your config
- Both "The Oracle" (FreqAI model) and "OracleSurfer" (strategy) will be visible in the web UI
- The web UI shows real-time data, trades, and FreqAI predictions

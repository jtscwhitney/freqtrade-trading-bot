# Accessing Oracle Predictions via Freqtrade API

## Quick Access Guide

### 1. Web UI Access
- **URL**: http://localhost:8080
- **Username**: `freqtrader`
- **Password**: `SuperSecurePassword123`

### 2. API Authentication

The Freqtrade API uses JWT tokens for authentication. You need to:
1. Login via the web UI (which handles authentication automatically)
2. OR use the API login endpoint to get a token

### 3. Key API Endpoints for Oracle/FreqAI

#### Get Bot Status (includes FreqAI info)
```
GET http://localhost:8080/api/v1/status
```

#### Get FreqAI Predictions
```
GET http://localhost:8080/api/v1/freqai/predictions
```

#### Get FreqAI Model Info
```
GET http://localhost:8080/api/v1/freqai/info
```

#### Get Current Trades (shows FreqAI data if available)
```
GET http://localhost:8080/api/v1/trades
```

#### Get Open Trades
```
GET http://localhost:8080/api/v1/trades/open
```

### 4. Authentication Methods

#### Method A: Via Web UI (Easiest)
1. Open http://localhost:8080 in your browser
2. Login with credentials above
3. The web UI automatically handles authentication
4. Navigate to the dashboard to see Oracle predictions

#### Method B: Via API Token (For Scripts/Programs)

**Step 1: Get JWT Token**
```bash
curl -X POST http://localhost:8080/api/v1/token/login \
  -H "Content-Type: application/json" \
  -d '{"username": "freqtrader", "password": "SuperSecurePassword123"}'
```

**Step 2: Use Token in Requests**
```bash
curl -X GET http://localhost:8080/api/v1/status \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 5. What Oracle Data You'll See

The API responses will include:
- **Regime Predictions**: BULL, BEAR, or NEUTRAL
- **Confidence Scores**: Probability for each regime
- **Prediction Timestamps**: When the prediction was made
- **Model Information**: Which FreqAI model is being used
- **Pair Information**: Which trading pairs have predictions

### 6. Example API Response Structure

**Status Endpoint Response:**
```json
{
  "state": "running",
  "strategy": "OracleSurfer_v12_PROD",
  "freqai": {
    "enabled": true,
    "model": "XGBoostClassifier",
    "predictions": {
      "BTC/USDT:USDT": {
        "regime": "BULL",
        "confidence": {
          "BEAR": 0.0149,
          "NEUTRAL": 0.0000,
          "BULL": 0.9851
        },
        "timestamp": "2026-02-04T18:43:19Z"
      }
    }
  }
}
```

### 7. Browser Access (No Scripts Needed)

The easiest way is to simply:
1. Open http://localhost:8080
2. Login
3. Navigate through the web UI
4. Look for FreqAI/Oracle sections in the dashboard

The web UI will display:
- Current Oracle regime predictions
- Strategy performance
- Trade history
- Real-time updates

### 8. Testing API Access

You can test if the API is working with:
```bash
curl http://localhost:8080/api/v1/ping
```

Should return: `{"status":"pong"}`

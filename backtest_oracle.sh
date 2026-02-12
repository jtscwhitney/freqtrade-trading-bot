#!/bin/bash
# Backtest script to force FreqAI training for RegimeValidation strategy
# This will train the model immediately, then you can use it in live mode

echo "========================================"
echo "FORCING FREQAI TRAINING VIA BACKTEST"
echo "========================================"
echo ""

docker exec freqtrade freqtrade backtesting \
  --config /freqtrade/user_data/config_oracle.json \
  --strategy RegimeValidation \
  --freqaimodel XGBoostClassifier \
  --timerange 20250101- \
  --userdir /freqtrade/user_data \
  -v

echo ""
echo "========================================"
echo "BACKTEST COMPLETE - Model should now be trained"
echo "========================================"

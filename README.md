# Freqtrade Algorithmic Trading Bot

A professional algorithmic trading bot built with the Freqtrade framework, designed to run in Docker containers for easy deployment and management.

## 🚀 Features

- **Automated Trading**: Execute trades based on technical analysis strategies
- **Multiple Strategies**: Includes a custom RSI-based strategy with configurable parameters
- **Risk Management**: Built-in stop-loss, take-profit, and position sizing
- **Real-time Monitoring**: Web interface and API for monitoring and control
- **Backtesting**: Test strategies on historical data
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Multi-exchange Support**: Compatible with major cryptocurrency exchanges

## 🏗️ Architecture

The project consists of three main services:

1. **Trading Bot** (`freqtrade`): Main trading engine that executes strategies
2. **Web Interface** (`freqtrade_webserver`): Dashboard for monitoring and control
3. **API Server** (`freqtrade_api`): REST API for programmatic access

## 📋 Prerequisites

- Docker and Docker Compose installed
- WSL2 (Windows Subsystem for Linux) or Ubuntu
- At least 4GB RAM available
- Stable internet connection

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/jtscwhitney/freqtrade-trading-bot.git
cd freqtrade-trading-bot
```

### 2. Configure Your Exchange API Keys

Edit `config/config.json` and add your exchange API credentials:

```json
{
    "exchange": {
        "name": "binance",
        "key": "your-api-key",
        "secret": "your-api-secret"
    }
}
```

**⚠️ Security Note**: Never commit API keys to version control. Use environment variables or secure secret management.

### 3. Start the Services

```bash
docker-compose up -d
```

This will start all three services:
- Trading Bot: http://localhost:8080
- Web Interface: http://localhost:8081
- API Server: http://localhost:9001

### 4. Access the Web Interface

Open your browser and navigate to `http://localhost:8081` to access the Freqtrade dashboard.

## 📊 Strategy Configuration

### RSI Strategy

The included `RSIStrategy` uses the Relative Strength Index to identify entry and exit points:

- **Entry Conditions**:
  - RSI below 30 (oversold)
  - Price near Bollinger Band lower band
  - MACD line above signal line
  - Volume above average
  - Low volatility

- **Exit Conditions**:
  - RSI above 70 (overbought)
  - Price near Bollinger Band upper band
  - MACD line below signal line

### Strategy Parameters

You can customize the strategy by modifying these parameters in `user_data/strategies/RSIStrategy.py`:

```python
# RSI parameters
rsi_period = IntParameter(10, 25, default=14, space="buy")
rsi_oversold = IntParameter(20, 35, default=30, space="buy")
rsi_overbought = IntParameter(65, 80, default=70, space="sell")
```

## 🔧 Configuration

### Main Configuration (`config/config.json`)

Key configuration options:

- **`max_open_trades`**: Maximum number of concurrent trades
- **`stake_amount`**: Amount to invest per trade
- **`timeframe`**: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
- **`dry_run`**: Set to `false` for live trading
- **`pair_whitelist`**: List of trading pairs

### Environment Variables

You can override configuration using environment variables:

```bash
export FT_PROVIDER=ccxt
export FT_DRY_RUN=true
export FT_STRATEGY=RSIStrategy
```

## 📈 Usage Examples

### Start Trading

```bash
# Start the trading bot
docker-compose up freqtrade

# Start with specific strategy
docker-compose run --rm freqtrade trade --strategy RSIStrategy
```

### Backtesting

```bash
# Run backtest on historical data
docker-compose run --rm freqtrade backtesting \
    --strategy RSIStrategy \
    --timerange 20230101-20231231
```

### Download Data

```bash
# Download historical data for backtesting
docker-compose run --rm freqtrade download-data \
    --exchange binance \
    --pairs BTC/USDT ETH/USDT \
    --timeframe 5m
```

### Strategy Optimization

```bash
# Optimize strategy parameters
docker-compose run --rm freqtrade hyperopt \
    --strategy RSIStrategy \
    --hyperopt-loss SharpeHyperOptLoss \
    --epochs 100
```

## 📊 Monitoring and Control

### Web Interface

The web interface provides:
- Real-time trade monitoring
- Performance analytics
- Strategy configuration
- Manual trade execution

### API Endpoints

Key API endpoints:

- `GET /api/v1/status`: Bot status
- `GET /api/v1/profit`: Profit summary
- `GET /api/v1/trades`: Trade history
- `POST /api/v1/start`: Start trading
- `POST /api/v1/stop`: Stop trading

### Logs

View logs for each service:

```bash
# Trading bot logs
docker-compose logs freqtrade

# Web interface logs
docker-compose logs freqtrade_webserver

# API server logs
docker-compose logs freqtrade_api
```

## 🔒 Security Considerations

1. **API Keys**: Store exchange API keys securely
2. **Network Security**: Use VPN if trading from public networks
3. **Access Control**: Implement authentication for web interface and API
4. **Monitoring**: Set up alerts for unusual trading activity

## 🧪 Testing

### Dry Run Mode

Always test strategies in dry-run mode first:

```json
{
    "dry_run": true,
    "dry_run_wallet": 1000
}
```

### Paper Trading

Use paper trading to test with real market data but fake money.

## 📚 Advanced Features

### Custom Strategies

Create your own strategies by extending the `IStrategy` class:

```python
from freqtrade.strategy import IStrategy

class MyStrategy(IStrategy):
    minimal_roi = {"0": 0.05}
    stoploss = -0.025
    
    def populate_indicators(self, dataframe, metadata):
        # Add your indicators here
        return dataframe
    
    def populate_entry_trend(self, dataframe, metadata):
        # Define entry conditions
        return dataframe
    
    def populate_exit_trend(self, dataframe, metadata):
        # Define exit conditions
        return dataframe
```

### Telegram Integration

Enable Telegram notifications:

```json
{
    "telegram": {
        "enabled": true,
        "token": "your-bot-token",
        "chat_id": "your-chat-id"
    }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Container won't start**: Check Docker logs and ensure ports are available
2. **API connection errors**: Verify exchange API keys and permissions
3. **Strategy errors**: Check strategy syntax and dependencies
4. **Performance issues**: Monitor system resources and optimize strategy

### Debug Mode

Enable debug logging:

```bash
docker-compose run --rm freqtrade trade --verbosity debug
```

## 📈 Performance Optimization

1. **Strategy Efficiency**: Optimize indicator calculations
2. **Timeframe Selection**: Choose appropriate timeframes for your strategy
3. **Risk Management**: Implement proper position sizing and stop-losses
4. **Backtesting**: Thoroughly test strategies before live trading

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Use at your own risk. Cryptocurrency trading involves substantial risk and may result in the loss of your invested capital. Past performance does not guarantee future results.

## 🆘 Support

- **Documentation**: [Freqtrade Docs](https://www.freqtrade.io/en/latest/)
- **Community**: [Freqtrade Discord](https://discord.gg/2zqj5x9)
- **Issues**: Create an issue in this repository

## 🔄 Updates

Keep your bot updated:

```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose down
docker-compose up -d
```

---

**Happy Trading! 🚀📈**
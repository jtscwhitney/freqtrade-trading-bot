@echo off
REM Merge Freqtrade Backtest Trades with Oracle Signals
REM Usage: merge_trades_with_oracle.bat [trades_file] [freqai_id] [output_file]

echo ========================================
echo MERGE TRADES WITH ORACLE SIGNALS
echo ========================================
echo.

if "%1"=="" (
    echo Usage: merge_trades_with_oracle.bat [trades_file] [freqai_id] [output_file]
    echo.
    echo Examples:
    echo   merge_trades_with_oracle.bat user_data\backtest_results\backtest-result.json Oracle_Surfer_DryRun trades_with_oracle.csv
    echo   merge_trades_with_oracle.bat user_data\backtest_results\*.json Oracle_Surfer_DryRun trades_with_oracle.csv
    echo.
    pause
    exit /b 1
)

set TRADES_FILE=%1
set FREQAI_ID=%2
set OUTPUT_FILE=%3

if "%FREQAI_ID"=="" (
    echo [ERROR] FreqAI identifier required
    echo Example: Oracle_Surfer_DryRun or Regime_Oracle_v7_Futures
    pause
    exit /b 1
)

if "%OUTPUT_FILE"=="" (
    set OUTPUT_FILE=trades_with_oracle.csv
)

echo Trades File: %TRADES_FILE%
echo FreqAI ID: %FREQAI_ID%
echo Output File: %OUTPUT_FILE%
echo.

python merge_trades_with_oracle.py --trades "%TRADES_FILE%" --freqai-id "%FREQAI_ID%" --output "%OUTPUT_FILE%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Merge failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo Output saved to: %OUTPUT_FILE%
echo.
pause

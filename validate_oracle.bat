@echo off
REM Oracle Validation Script
REM Runs a backtest and validates Oracle predictions

echo ========================================
echo ORACLE VALIDATION TEST
echo ========================================
echo.
echo This will:
echo 1. Run a backtest on historical data
echo 2. Check if Oracle produces predictions
echo 3. Verify probabilities change over time
echo 4. Validate model functionality
echo.
pause

echo.
echo Running backtest...
docker exec freqtrade freqtrade backtesting ^
  --config /freqtrade/user_data/config_oracle.json ^
  --strategy RegimeValidation ^
  --freqaimodel XGBoostClassifier ^
  --timerange 20250101- ^
  --userdir /freqtrade/user_data ^
  -v > backtest_validation_output.txt 2>&1

echo.
echo ========================================
echo Analyzing results...
echo ========================================

REM Check for predictions in the output
findstr /C:"Found class probabilities" backtest_validation_output.txt > nul
if %errorlevel% == 0 (
    echo [OK] Oracle produced predictions
) else (
    echo [FAIL] No predictions found
)

REM Check for probability changes
findstr /C:"Probability changed" backtest_validation_output.txt > nul
if %errorlevel% == 0 (
    echo [OK] Probabilities changed over time
) else (
    echo [WARN] No probability changes detected
)

REM Check for training completion
findstr /C:"Done training" backtest_validation_output.txt > nul
if %errorlevel% == 0 (
    echo [OK] Model training completed
) else (
    echo [FAIL] Training may not have completed
)

echo.
echo ========================================
echo Full output saved to: backtest_validation_output.txt
echo ========================================
echo.
echo To see detailed predictions, run:
echo   python validate_oracle.py
echo.
pause

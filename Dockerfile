# Start from the FreqAI-ready image
FROM freqtradeorg/freqtrade:stable_freqai

# Switch to root user to install packages
USER root

# Install pandas_ta
RUN pip install pandas_ta pyzmq

# Switch back to the standard user for security
USER ftuser
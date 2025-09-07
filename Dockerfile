FROM ghcr.io/freqtrade/freqtrade:stable

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib (Technical Analysis Library)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# Copy requirements and install Python packages
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create necessary directories
RUN mkdir -p /freqtrade/user_data/strategies \
    /freqtrade/user_data/data \
    /freqtrade/user_data/logs \
    /freqtrade/user_data/backtest_results

# Set working directory
WORKDIR /freqtrade

# Default command
CMD ["trade", "--help"]


# Dual Momentum Trading Bot

An automated stock and crypto portfolio bot built in Python, using Gary Antonacci's **Dual Momentum** strategy — one of the most evidence-backed systematic investing approaches available to retail investors.

## Strategy Overview

Every rebalance cycle the bot asks two questions about each asset:

1. **Absolute Momentum** — Is this asset outperforming cash (T-bills)? If not, rotate to a safe haven (bonds).
2. **Relative Momentum** — Of the assets that pass the absolute test, which ones have the strongest 12-month performance?

It buys the top performers and holds them until the next rebalance. Stocks rebalance monthly. Crypto rebalances weekly.

## Portfolio Structure

| Sleeve | Allocation | Assets |
|---|---|---|
| Stocks / ETFs | 65% | SPY, QQQ, IWM, sector ETFs, NVDA, META, MSFT, AMZN |
| Crypto | 35% | BTC (core), ETH (core), SOL / AVAX / LINK (rotating) |

## Tech Stack

- **Python 3** — core language
- **Alpaca API** — brokerage (paper + live trading, $0 commission)
- **yfinance** — free historical price data for momentum calculation
- **alpaca-py** — official Alpaca SDK

## Setup

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Add your Alpaca API keys to config.py

# 3. Run
python3 bot.py
```

Full step-by-step setup guide available in project documentation.

## Risk Management

- Monthly/weekly rebalancing (not day trading)
- Absolute momentum filter rotates to bonds in bear markets
- 20% peak-to-trough drawdown alert via email
- Trade journal logged to CSV for review

## Disclaimer

Built for educational purposes and paper trading. Past performance of any strategy does not guarantee future results. Only invest money you can afford to lose.

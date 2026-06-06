"""
config.py — The only file you need to edit.
Step 1: Add your Alpaca API keys (free at https://app.alpaca.markets)
Step 2: Everything else is pre-configured and ready to go.
"""

# ── Alpaca API Keys ────────────────────────────────────────────────────────────
# Sign up at https://app.alpaca.markets → Overview → API Keys
API_KEY    = "Your API"
SECRET_KEY = "Your Secret Key"

# ALWAYS start with True. Change to False only when going live with real money.
PAPER_TRADING = True

# ── Portfolio Allocation ───────────────────────────────────────────────────────
# How to split the portfolio between stocks and crypto
STOCK_ALLOCATION_PCT  = 0.65   # 65% of portfolio in stocks/ETFs
CRYPTO_ALLOCATION_PCT = 0.35   # 35% of portfolio in crypto

# ── Stock Universe ─────────────────────────────────────────────────────────────
# The bot picks the best performers from this list each month.
# Mix of broad market, sectors, and international — gives the momentum filter
# plenty to rotate between depending on what's leading.
STOCK_UNIVERSE = [
    # Broad US market
    "SPY",    # S&P 500 — the benchmark
    "QQQ",    # Nasdaq 100 — tech heavy, high growth
    "IWM",    # Russell 2000 — small caps, higher beta

    # Sectors that tend to lead in growth cycles
    "XLK",    # Technology
    "XLY",    # Consumer Discretionary (Amazon, Tesla etc.)
    "XLF",    # Financials

    # International (for true diversification)
    "EFA",    # Developed markets ex-US (Europe, Japan, Australia)
    "EEM",    # Emerging markets (China, India, Brazil etc.)

    # Individual high-momentum names
    "NVDA",   # NVIDIA — AI infrastructure leader
    "META",   # Meta — strong earnings growth
    "MSFT",   # Microsoft — cloud + AI
    "AMZN",   # Amazon — e-commerce + AWS
]

# How many top stocks to hold at once
TOP_N_STOCKS = 4

# If nothing passes the momentum filter, rotate here (safe haven)
SAFE_HAVEN_TICKER = "BND"   # Vanguard Total Bond Market ETF

# Proxy for "cash rate" hurdle (3-month T-bill performance)
CASH_PROXY_TICKER = "BIL"

# ── Crypto Universe ────────────────────────────────────────────────────────────
# The bot always cores around BTC and ETH, then picks the best alt.
# These were selected based on:
#   - Market cap and liquidity (reduces manipulation risk)
#   - Strong network fundamentals
#   - Available on Alpaca
CRYPTO_UNIVERSE = [
    "BTC/USD",   # Bitcoin — digital gold, store of value
    "ETH/USD",   # Ethereum — smart contracts, DeFi backbone
    "SOL/USD",   # Solana — fast L1, strong developer ecosystem
    "AVAX/USD",  # Avalanche — growing DeFi and gaming ecosystem
    "LINK/USD",  # Chainlink — oracle infrastructure, essential to DeFi
]

# How many crypto assets to hold at once (BTC + ETH + 1 alt = 3 is the default)
TOP_N_CRYPTO = 3

# ── Rebalance Schedule ─────────────────────────────────────────────────────────
REBALANCE_DAYS_STOCK  = 30   # Rebalance stocks monthly
REBALANCE_DAYS_CRYPTO = 7    # Rebalance crypto weekly (more volatile)

# ── Momentum Lookback ──────────────────────────────────────────────────────────
MOMENTUM_LOOKBACK_DAYS = 252   # ~12 months trading days for stocks
# (Crypto uses 90 days, set in bot.py)

# ── Email Alerts (optional) ───────────────────────────────────────────────────
# Leave blank to skip. To enable:
#   - Use a Gmail account
#   - Generate an App Password: Google Account → Security → App Passwords
ALERT_EMAIL          = ""    # e.g. "mybot@gmail.com"
ALERT_EMAIL_PASSWORD = ""    # Gmail App Password (16 chars, no spaces)
ALERT_EMAIL_TO       = ""    # Where alerts go, e.g. "me@gmail.com"

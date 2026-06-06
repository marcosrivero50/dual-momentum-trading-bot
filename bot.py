"""
================================================================================
  Dual Momentum Portfolio Bot
  Strategy: Gary Antonacci's Dual Momentum (Absolute + Relative)
  Assets  : US Stocks, International ETFs, Bonds (safe haven), BTC/ETH/Crypto
  Rebalance: Every 30 days — swing trader, not day trader
  Platform : Alpaca (paper + live)
================================================================================

HOW IT WORKS (plain English):
  Every 30 days the bot asks two questions about each asset:
    1. Absolute Momentum: "Is this doing better than cash (T-bills)?"
       → If no, skip it. If yes, consider buying.
    2. Relative Momentum: "Which of the eligible assets has performed best
       over the past 12 months?"
       → Buy the top performers. Hold until next rebalance.

  This sounds simple. That's the point. It has 40+ years of evidence behind it.
  It sidesteps bad markets automatically (absolute filter) and rotates into
  strength (relative ranking). No emotions, no noise, no 20 trades a day.

  Crypto runs on the same logic but rebalances weekly (more volatile, moves faster).
"""

import time
import logging
import json
import os
from datetime import datetime, timedelta, date

import yfinance as yf
import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import (
    API_KEY, SECRET_KEY, PAPER_TRADING,
    STOCK_UNIVERSE, CRYPTO_UNIVERSE,
    TOP_N_STOCKS, TOP_N_CRYPTO,
    STOCK_ALLOCATION_PCT, CRYPTO_ALLOCATION_PCT,
    MOMENTUM_LOOKBACK_DAYS, REBALANCE_DAYS_STOCK, REBALANCE_DAYS_CRYPTO,
    SAFE_HAVEN_TICKER, CASH_PROXY_TICKER,
)
from risk_manager import RiskManager
from trade_journal import TradeJournal

# ── Logging ────────────────────────────────────────────────────────────────────
import sys, io
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)),
    ],
)
log = logging.getLogger(__name__)


class DualMomentumBot:
    def __init__(self):
        self.trading  = TradingClient(API_KEY, SECRET_KEY, paper=PAPER_TRADING)
        self.stock_data = StockHistoricalDataClient(API_KEY, SECRET_KEY)
        self.crypto_data = CryptoHistoricalDataClient(API_KEY, SECRET_KEY)
        self.risk    = RiskManager()
        self.journal = TradeJournal()

        # Track last rebalance dates — loaded from disk so restarts don't re-run
        self.state_file = "bot_state.json"
        self.last_stock_rebalance  = None
        self.last_crypto_rebalance = None
        self._load_state()

        log.info("=" * 60)
        log.info("  Dual Momentum Bot  |  Paper=%s", PAPER_TRADING)
        log.info("=" * 60)
        self._log_account()

    # ── State persistence ─────────────────────────────────────────────────────

    def _load_state(self):
        """Load last rebalance dates from disk so restarts don't trigger duplicate rebalances."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    s = json.load(f)
                if s.get("last_stock_rebalance"):
                    self.last_stock_rebalance = date.fromisoformat(s["last_stock_rebalance"])
                    log.info("  Loaded state: last stock rebalance was %s", self.last_stock_rebalance)
                if s.get("last_crypto_rebalance"):
                    self.last_crypto_rebalance = date.fromisoformat(s["last_crypto_rebalance"])
                    log.info("  Loaded state: last crypto rebalance was %s", self.last_crypto_rebalance)
            except Exception as e:
                log.warning("Could not load state file: %s", e)
        else:
            log.info("  No state file found — first run detected.")

    def _save_state(self):
        """Save last rebalance dates to disk."""
        try:
            s = {
                "last_stock_rebalance":  self.last_stock_rebalance.isoformat()  if self.last_stock_rebalance  else None,
                "last_crypto_rebalance": self.last_crypto_rebalance.isoformat() if self.last_crypto_rebalance else None,
            }
            with open(self.state_file, "w") as f:
                json.dump(s, f, indent=2)
        except Exception as e:
            log.warning("Could not save state file: %s", e)

    # ── Account helpers ────────────────────────────────────────────────────────

    def _log_account(self):
        acc = self.trading.get_account()
        log.info("  Equity      : $%.2f", float(acc.equity))
        log.info("  Buying Power: $%.2f", float(acc.buying_power))
        log.info("  Cash        : $%.2f", float(acc.cash))
        return float(acc.equity)

    def _equity(self):
        return float(self.trading.get_account().equity)

    def _buying_power(self):
        return float(self.trading.get_account().buying_power)

    def _get_positions(self):
        """Returns {symbol: qty} for all open positions."""
        try:
            return {p.symbol: float(p.qty) for p in self.trading.get_all_positions()}
        except Exception:
            return {}

    # ── Momentum calculation ───────────────────────────────────────────────────

    def _momentum_score(self, ticker: str, days: int = None) -> float:
        """
        Returns the total return over the lookback period.
        Positive = momentum is positive (asset trending up).
        Uses yfinance which is free and needs no API key.
        """
        days = days or MOMENTUM_LOOKBACK_DAYS
        try:
            hist = yf.Ticker(ticker).history(period=f"{days + 10}d")
            if len(hist) < 20:
                return 0.0
            start_price = float(hist["Close"].iloc[-(days)])
            end_price   = float(hist["Close"].iloc[-1])
            return (end_price - start_price) / start_price
        except Exception as e:
            log.warning("Momentum error for %s: %s", ticker, e)
            return 0.0

    def _cash_rate(self) -> float:
        """Returns approximate 3-month T-bill yield as the absolute momentum hurdle."""
        try:
            # BIL is the SPDR Bloomberg 1-3 Month T-Bill ETF — free proxy for cash rate
            bil = yf.Ticker("BIL").history(period="400d")
            if len(bil) < 200:
                return 0.01  # fallback 1%
            start = float(bil["Close"].iloc[-MOMENTUM_LOOKBACK_DAYS])
            end   = float(bil["Close"].iloc[-1])
            return (end - start) / start
        except Exception:
            return 0.01  # fallback

    # ── Order helpers ──────────────────────────────────────────────────────────

    def _market_value(self, symbol: str) -> float:
        """Current dollar value of a held position."""
        try:
            p = self.trading.get_open_position(symbol)
            return float(p.market_value)
        except Exception:
            return 0.0

    def _place_buy(self, symbol: str, dollar_amount: float, asset_class: str = "stock"):
        """Buy a dollar amount of a symbol using fractional shares where possible."""
        try:
            price = self._current_price(symbol, asset_class)
            if price <= 0:
                log.warning("Could not get price for %s, skipping buy", symbol)
                return

            qty = round(dollar_amount / price, 4)
            if qty <= 0:
                return

            # Alpaca fractional shares use notional for stocks
            if asset_class == "stock":
                req = MarketOrderRequest(
                    symbol=symbol,
                    notional=round(dollar_amount, 2),
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                # Crypto: use qty (fractional)
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                )

            self.trading.submit_order(req)
            self.journal.log("BUY", symbol, qty, price, asset_class=asset_class)
            log.info("  [BUY]  %-8s  $%.0f  (~%.4f units @ $%.2f)", symbol, dollar_amount, qty, price)

        except Exception as e:
            log.error("  Buy error for %s: %s", symbol, e)

    def _place_sell(self, symbol: str, qty: float, asset_class: str = "stock"):
        """Sell entire position."""
        try:
            price = self._current_price(symbol, asset_class)
            if asset_class == "stock":
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=round(qty, 6),
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=round(qty, 6),
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                )

            self.trading.submit_order(req)
            self.journal.log("SELL", symbol, qty, price, asset_class=asset_class)
            log.info("  [SELL] %-8s  %.4f units", symbol, qty)

        except Exception as e:
            log.error("  Sell error for %s: %s", symbol, e)

    def _current_price(self, symbol: str, asset_class: str = "stock") -> float:
        try:
            if asset_class == "crypto":
                # Convert Alpaca format (BTCUSD) to Yahoo format (BTC-USD)
                # Alpaca strips the slash: BTC/USD -> BTCUSD
                # Yahoo needs a dash: BTC-USD
                yf_symbol = symbol.replace("USD", "-USD") if not "-" in symbol else symbol
            else:
                yf_symbol = symbol
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return 0.0
        except Exception:
            return 0.0

    def _close_all_positions_in(self, symbols: list):
        """Sell any currently held positions that are not in the target list."""
        positions = self._get_positions()
        for sym, qty in positions.items():
            if sym not in symbols:
                log.info("  Rotating out of %s (not in new target list)", sym)
                asset_class = "crypto" if "/" in sym or sym in [s.replace("/USD","") for s in CRYPTO_UNIVERSE] else "stock"
                self._place_sell(sym, qty, asset_class=asset_class)

    # ── Core strategy ──────────────────────────────────────────────────────────

    def rebalance_stocks(self):
        """
        Dual Momentum rebalance for the stock sleeve.
        1. Score each asset in STOCK_UNIVERSE by 12-month momentum
        2. Absolute filter: only keep if > cash (T-bill) rate
        3. Rank survivors, pick TOP_N_STOCKS
        4. Sell anything not in the new top, buy into new top
        """
        log.info("")
        log.info("── STOCK REBALANCE ─────────────────────────────────────────")

        cash_rate = self._cash_rate()
        log.info("  Cash hurdle (T-bill proxy): %.2f%%", cash_rate * 100)

        scores = {}
        for ticker in STOCK_UNIVERSE:
            m = self._momentum_score(ticker)
            log.info("  %-6s  12m momentum: %+.1f%%", ticker, m * 100)
            if m > cash_rate:  # absolute momentum filter
                scores[ticker] = m
            else:
                log.info("         → fails absolute filter (below cash rate), skipped")

        if not scores:
            log.warning("  No assets pass absolute filter — rotating to safe haven (%s)", SAFE_HAVEN_TICKER)
            target = [SAFE_HAVEN_TICKER]
        else:
            ranked = sorted(scores, key=scores.get, reverse=True)
            target = ranked[:TOP_N_STOCKS]
            log.info("  Top %d selected: %s", TOP_N_STOCKS, target)

        # Sell anything not in target
        positions = self._get_positions()
        for sym, qty in positions.items():
            if sym not in target and sym in STOCK_UNIVERSE + [SAFE_HAVEN_TICKER]:
                self._place_sell(sym, qty, asset_class="stock")

        # Buy equal weight into each target
        equity = self._equity()
        stock_budget = equity * STOCK_ALLOCATION_PCT
        per_position = stock_budget / len(target)

        for sym in target:
            current_val = self._market_value(sym)
            diff = per_position - current_val
            if diff > 10:  # only buy if meaningfully underweight
                self._place_buy(sym, diff, asset_class="stock")
            elif diff < -10:  # trim if overweight
                price = self._current_price(sym, "stock")
                if price > 0:
                    trim_qty = abs(diff) / price
                    self._place_sell(sym, trim_qty, asset_class="stock")

        self.last_stock_rebalance = date.today()
        self._save_state()
        self.journal.save()
        log.info("  Stock rebalance complete.")

    def rebalance_crypto(self):
        """
        Momentum rebalance for the crypto sleeve.
        Uses a shorter lookback (90 days) since crypto moves faster.
        Always holds BTC/ETH as core + best-momentum altcoins.
        """
        log.info("")
        log.info("── CRYPTO REBALANCE ────────────────────────────────────────")

        # BTC and ETH are always core — score them too but won't drop them unless
        # absolute momentum is deeply negative
        scores = {}
        for pair in CRYPTO_UNIVERSE:
            ticker = pair.replace("/", "-")  # yfinance format: BTC-USD
            m = self._momentum_score(ticker, days=90)
            log.info("  %-10s  90d momentum: %+.1f%%", pair, m * 100)
            # Absolute filter: only drop if momentum is very negative (< -20%)
            # We're more lenient on crypto since crypto corrections are frequent
            if m > -0.20:
                scores[pair] = m
            else:
                log.info("         → deeply negative, skipped this cycle")

        if not scores:
            log.warning("  All crypto deeply negative — holding cash this cycle")
            # Sell everything in crypto universe
            positions = self._get_positions()
            for sym, qty in positions.items():
                if sym in [p.replace("/", "") for p in CRYPTO_UNIVERSE]:
                    self._place_sell(sym, qty, asset_class="crypto")
            return

        ranked = sorted(scores, key=scores.get, reverse=True)
        target = ranked[:TOP_N_CRYPTO]
        log.info("  Top %d crypto selected: %s", TOP_N_CRYPTO, target)

        equity = self._equity()
        crypto_budget = equity * CRYPTO_ALLOCATION_PCT

        # Weight: BTC 40%, ETH 30%, rest split equally
        weights = {}
        core = [p for p in target if "BTC" in p or "ETH" in p]
        alts = [p for p in target if p not in core]

        if "BTC/USD" in target:
            weights["BTC/USD"] = 0.40
        if "ETH/USD" in target:
            weights["ETH/USD"] = 0.30
        remaining = 1.0 - sum(weights.values())
        if alts:
            per_alt = remaining / len(alts)
            for a in alts:
                weights[a] = per_alt

        for pair, weight in weights.items():
            alloc = crypto_budget * weight
            sym = pair.replace("/", "")  # Alpaca crypto format: BTCUSD
            self._place_buy(sym, alloc, asset_class="crypto")

        self.last_crypto_rebalance = date.today()
        self._save_state()
        self.journal.save()
        log.info("  Crypto rebalance complete.")

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def _should_rebalance_stocks(self) -> bool:
        if self.last_stock_rebalance is None:
            return True
        return (date.today() - self.last_stock_rebalance).days >= REBALANCE_DAYS_STOCK

    def _should_rebalance_crypto(self) -> bool:
        if self.last_crypto_rebalance is None:
            return True
        return (date.today() - self.last_crypto_rebalance).days >= REBALANCE_DAYS_CRYPTO

    def run(self):
        """Main loop — checks daily whether rebalance is due."""
        log.info("")
        log.info("  Bot running. Stocks rebalance every %dd, Crypto every %dd.",
                 REBALANCE_DAYS_STOCK, REBALANCE_DAYS_CRYPTO)
        log.info("  Press Ctrl+C to stop.")

        while True:
            try:
                log.info("")
                log.info("── Daily Check @ %s ─────────────────────────────────",
                         datetime.now().strftime("%Y-%m-%d %H:%M"))

                # Portfolio health check
                equity = self._equity()
                self.risk.check(equity)

                if self._should_rebalance_stocks():
                    self.rebalance_stocks()
                else:
                    days_left = REBALANCE_DAYS_STOCK - (date.today() - self.last_stock_rebalance).days
                    log.info("  Stock rebalance in %d day(s).", days_left)

                if self._should_rebalance_crypto():
                    self.rebalance_crypto()
                else:
                    days_left = REBALANCE_DAYS_CRYPTO - (date.today() - self.last_crypto_rebalance).days
                    log.info("  Crypto rebalance in %d day(s).", days_left)

                self._log_account()

            except KeyboardInterrupt:
                log.info("Bot stopped by user.")
                break
            except Exception as e:
                log.error("Main loop error: %s", e)

            # Check once per day
            log.info("  Sleeping 24h until next check...")
            time.sleep(86400)


if __name__ == "__main__":
    bot = DualMomentumBot()
    bot.run()

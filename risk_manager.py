"""
risk_manager.py — Portfolio-level protection.
Monitors total equity and sends an alert if the portfolio drops
more than MAX_DRAWDOWN_PCT from its peak value.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

log = logging.getLogger(__name__)

MAX_DRAWDOWN_PCT = 0.20   # Alert if down 20% from peak equity


class RiskManager:
    def __init__(self):
        self.peak_equity = None

    def check(self, current_equity: float):
        """Call once per daily loop. Tracks peak and warns on large drawdown."""
        if self.peak_equity is None or current_equity > self.peak_equity:
            self.peak_equity = current_equity

        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        log.info("  Peak equity: $%.2f | Current: $%.2f | Drawdown: %.1f%%",
                 self.peak_equity, current_equity, drawdown * 100)

        if drawdown >= MAX_DRAWDOWN_PCT:
            log.warning("⚠️  DRAWDOWN ALERT: Portfolio is down %.1f%% from peak!", drawdown * 100)
            self._send_alert(current_equity, drawdown)

    def _send_alert(self, equity: float, drawdown: float):
        try:
            from config import ALERT_EMAIL, ALERT_EMAIL_PASSWORD, ALERT_EMAIL_TO
            if not ALERT_EMAIL or not ALERT_EMAIL_TO:
                return

            body = (
                f"Portfolio Drawdown Alert — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Your bot portfolio has dropped {drawdown*100:.1f}% from its peak.\n"
                f"Current equity: ${equity:,.2f}\n"
                f"Peak equity: ${self.peak_equity:,.2f}\n\n"
                f"Review bot.log for full details."
            )
            msg = MIMEText(body)
            msg["Subject"] = f"⚠️ Bot Alert: Portfolio Down {drawdown*100:.0f}%"
            msg["From"] = ALERT_EMAIL
            msg["To"]   = ALERT_EMAIL_TO

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(ALERT_EMAIL, ALERT_EMAIL_PASSWORD)
                s.send_message(msg)
            log.info("📧 Drawdown alert emailed.")
        except Exception as e:
            log.error("Email alert failed: %s", e)

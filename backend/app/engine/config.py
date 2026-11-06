import os
from dotenv import load_dotenv

# backend/ is the anchor for .env, the SQLite file and every cache directory,
# so the API, the jobs and the tests all resolve the same paths from any cwd.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# Model that narrates computed numbers (reasons text); never decides a score, price or date.
NARRATION_MODEL = os.getenv("NARRATION_MODEL", "claude-opus-5-5")
# The analyst view (docs/API_CONTRACT.md -> Analyst view): Opus 5.5, thinking always on, depth set by effort.
ANALYST_MODEL = os.getenv("ANALYST_MODEL", "claude-opus-5-5")
ANALYST_EFFORT = os.getenv("ANALYST_EFFORT", "medium")
# Nightly cap on new analyst views (each is a paid model call; cached views cost nothing).
ANALYST_MAX_VIEWS_PER_NIGHT = int(os.getenv("ANALYST_MAX_VIEWS_PER_NIGHT", "60"))

# Full Nifty 50 universe — system scans all and surfaces best signals
WATCHLIST = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "WIPRO", "BAJFINANCE", "AXISBANK", "LTIMINDTS",
    "SUNPHARMA", "ULTRACEMCO", "TITAN", "ASIANPAINT", "NESTLEIND",
    "MARUTI", "KOTAKBANK", "LT", "NTPC", "POWERGRID",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "ONGC", "BPCL",
    "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL",
    "HCLTECH", "TECHM", "INDUSINDBK", "BAJAJ-AUTO", "EICHERMOT",
    "HEROMOTOCO", "DIVISLAB", "DRREDDY", "CIPLA", "APOLLOHOSP",
    "BRITANNIA", "ITC", "HINDUNILVR", "BAJAJFINSV", "GRASIM",
    "SHREECEM", "M&M", "TRENT", "BEL", "BHARTIARTL",
]

# Period for historical data fetch
DATA_PERIOD = "6mo"
DATA_INTERVAL = "1d"

# Consensus thresholds
MIN_CONSENSUS_SOURCES = 3   # minimum agents that must agree
MIN_CONSENSUS_SCORE = 60    # out of 100

# Risk settings
DEFAULT_CAPITAL = 1000      # INR
MAX_RISK_PCT = 0.01         # 1% of capital per trade

# ── Emerging Opportunities scanner ──────────────────────────────────────────
# Local disk cache for NSE bhavcopy (free, full-market daily OHLCV+delivery data)
BHAVCOPY_CACHE_DIR = os.path.join(BACKEND_DIR, "data", "cache", "bhavcopy")
FUNDAMENTALS_CACHE_DIR = os.path.join(BACKEND_DIR, "data", "cache", "fundamentals")

# Cached full scan results (keyed by latest trading day + shortlist size), so
# opening the page doesn't re-run the whole funnel — including every yfinance
# fundamentals call — on every rerun/reload within the same trading day.
EMERGING_SCAN_CACHE_DIR = os.path.join(BACKEND_DIR, "data", "cache", "emerging_scan")

# How many calendar days of full-market history to build for the technical/
# volume/price-position prefilter (Stage 1). 400 calendar days (~270 trading
# days) so 52-week-high distance and the 200-day EMA are both meaningful.
BHAVCOPY_LOOKBACK_DAYS = 400

# Stage 1 (free, full NSE universe) -> Stage 2 (yfinance fundamentals) funnel.
# Only the top N technical/volume prefilter survivors get fundamentals fetched,
# to keep scans fast and avoid hammering yfinance across ~2000 stocks.
EMERGING_SHORTLIST_SIZE = 250
EMERGING_MIN_PRICE = 5          # exclude illiquid penny stocks
EMERGING_MIN_AVG_TURNOVER_LACS = 50   # exclude illiquid/untradeable names

# Emerging Opportunity Score weights (must sum to 100). Kept as a plain dict so
# they can be retuned without touching scoring logic.
EMERGING_SCORE_WEIGHTS = {
    "earnings_acceleration": 25,
    "fundamental_quality": 15,
    "early_price_position": 15,
    "volume_accumulation": 15,
    "technical_setup": 15,
    "valuation": 15,
}

# ── Application database ────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", os.path.join(BACKEND_DIR, "data", "trade_assistant.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

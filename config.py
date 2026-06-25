import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# --- TELEGRAM CONFIGURATION ---
# These are now loaded from the .env file or environment variables.
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

# --- SCANNER CONFIGURATION ---
SCAN_UNIVERSE = os.environ.get("SCAN_UNIVERSE", "Total Cash Segment")
SCAN_INTERVAL = os.environ.get("SCAN_INTERVAL", "1h")
SEND_IF_EMPTY = os.environ.get("SEND_IF_EMPTY", "True").lower() == "true"
LIVE_UNIVERSE_FETCH = os.environ.get("LIVE_UNIVERSE_FETCH", "False").lower() == "true"

# --- STRATEGY THRESHOLDS ---
STRATEGY_CONFIG = {
    "EMA": [5, 9, 21],          # EMA lengths for price comparison
    "STOCH_RSI_K_MIN": 70,      # Minimum Stoch RSI K level
    "SMI_MIN": 30,              # Minimum SMI level
    "MACD_MIN": 0.75,           # Minimum MACD level
    "STOCH_RSI": {
        "length": 14,
        "rsi_length": 14,
        "k": 3,
        "d": 3
    },
    "SMI": {
        "length": 10,
        "smooth": 3
    },
    "MACD": {
        "fast": 12,
        "slow": 26,
        "signal": 9
    }
}

# --- TRIGGER CONFIGURATION ---
TRIGGER_PORT = int(os.environ.get("TRIGGER_PORT", "8503"))

# --- TELEGRAM CSV CONFIGURATION ---
SEND_CSV = os.environ.get("SEND_CSV", "False").lower() == "true"


# --- LIQUIDITY CONFIGURATION ---
MIN_PRICE = float(os.environ.get("MIN_PRICE", "20.0"))
MIN_VOLUME_1D = int(os.environ.get("MIN_VOLUME_1D", "50000"))
MIN_VOLUME_1H = int(os.environ.get("MIN_VOLUME_1H", "10000"))
MIN_TURNOVER_1D = float(os.environ.get("MIN_TURNOVER_1D", "2500000.0")) # 25 Lakhs
MIN_TURNOVER_1H = float(os.environ.get("MIN_TURNOVER_1H", "500000.0"))   # 5 Lakhs




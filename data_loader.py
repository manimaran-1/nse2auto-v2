import pandas as pd
import requests
import io
import pytz
import logging
import os
import time
import hashlib
import pickle
import urllib.request
import json
import zipfile
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from datetime import datetime, timedelta

# Fix TzCache permission errors on Streamlit Cloud — use project cache dir
_tz_cache_dir = os.path.join(os.path.dirname(__file__), "cache", "tz_cache")
os.makedirs(_tz_cache_dir, exist_ok=True)
try:
    yf.set_tz_cache_location(_tz_cache_dir)
except Exception:
    pass

# Suppress yfinance's noisy stderr logging for missing/delisted symbols
yf_logger = logging.getLogger("yfinance")
yf_logger.setLevel(logging.CRITICAL)

# Configuration for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_now_ist():
    """
    Returns the current time in Indian Standard Time (IST), auto-correcting 
    for cases where the system clock is set to local Indian time but the OS 
    timezone is configured as UTC (double offset bug).
    """
    now_naive = datetime.now()
    import time
    is_system_utc = time.tzname[0] in ('UTC', 'GMT')
    
    if is_system_utc:
        try:
            if not hasattr(get_now_ist, "_is_double_offset"):
                # Use a fast HEAD request to Google to check true GMT time
                res = requests.head('https://www.google.com', timeout=1.0)
                gmt_str = res.headers.get('Date')
                if gmt_str:
                    gmt_dt = datetime.strptime(gmt_str, '%a, %d %b %Y %H:%M:%S GMT')
                    diff = abs((now_naive - gmt_dt).total_seconds())
                    # If difference is ~5.5 hours (19800 seconds), system clock is set to local Indian time
                    get_now_ist._is_double_offset = (18000 <= diff <= 21600)
                else:
                    get_now_ist._is_double_offset = False
            
            if get_now_ist._is_double_offset:
                # System clock naive time is already IST, just localize it without shifting
                return IST.localize(now_naive)
        except Exception:
            pass
            
    return datetime.now(IST)

# Symbol aliases — stocks renamed on NSE/Yahoo
SYMBOL_ALIASES = {
    "ZOMATO": "ETERNAL",
    "8K": "8KMILES",
}

# ============================================================
# STORAGE DIRECTORIES
# ============================================================
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
OHLCV_CACHE_DIR = os.path.join(CACHE_DIR, "ohlcv")
BHAVCOPY_CACHE_DIR = os.path.join(CACHE_DIR, "bhavcopy")
OHLCV_CACHE_MINUTES = 5  # OHLCV data cached for 5 min during market hours

# Permanent folder for stored universe files
PERMANENT_DIR = os.path.join(os.path.dirname(__file__), "universe_data")

# Ensure directories exist
for _d in [CACHE_DIR, OHLCV_CACHE_DIR, BHAVCOPY_CACHE_DIR, PERMANENT_DIR]:
    os.makedirs(_d, exist_ok=True)


def _ohlcv_cache_key(symbol, resolution, range_from, range_to):
    """Generate a unique, filesystem-safe cache key."""
    raw = f"{symbol}|{resolution}|{range_from}|{range_to}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_ohlcv_cache(symbol, resolution, range_from, range_to):
    """Return cached DataFrame if valid, else None. Uses parquet for safety."""
    key = _ohlcv_cache_key(symbol, resolution, range_from, range_to)
    parquet_path = os.path.join(OHLCV_CACHE_DIR, f"{key}.parquet")
    pkl_path = os.path.join(OHLCV_CACHE_DIR, f"{key}.pkl")

    cache_path = None
    if os.path.exists(parquet_path):
        cache_path = parquet_path
    elif os.path.exists(pkl_path):
        cache_path = pkl_path

    if cache_path is None:
        return None

    age_sec = time.time() - os.path.getmtime(cache_path)
    now_ist = get_now_ist()
    market_open = now_ist.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    if market_open <= now_ist <= market_close:
        max_age = OHLCV_CACHE_MINUTES * 60
    else:
        max_age = 3600  # 1 hour outside market

    if age_sec < max_age:
        try:
            if cache_path.endswith('.parquet'):
                return pd.read_parquet(cache_path)
            else:
                # Migrate old pickle to parquet — use context manager to close file handle
                with open(cache_path, "rb") as f:
                    df = pickle.load(f)
                try:
                    df.to_parquet(parquet_path)
                    os.remove(pkl_path)
                except Exception:
                    pass
                return df
        except Exception:
            return None
    return None


def _set_ohlcv_cache(symbol, resolution, range_from, range_to, df):
    """Persist DataFrame to disk cache using parquet format."""
    key = _ohlcv_cache_key(symbol, resolution, range_from, range_to)
    parquet_path = os.path.join(OHLCV_CACHE_DIR, f"{key}.parquet")
    try:
        df.to_parquet(parquet_path)
    except Exception as e:
        logger.debug(f"Cache write failed for {symbol}: {e}")


# ============================================================
# SYMBOL LIST FETCHING (Permanent folder / Live Fetch Toggle)
# ============================================================

# Persistent HTTP session for all web requests
_http_session = requests.Session()
_http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/',
})

def fetch_with_cache(url, filename, live_fetch=False):
    """Fetches a CSV from a URL. Defaults to reading from permanent storage if it exists."""
    perm_path = os.path.join(PERMANENT_DIR, filename)

    if not live_fetch and os.path.exists(perm_path):
        logger.info(f"Using stored permanent list: {filename}")
        try:
            return pd.read_csv(perm_path)
        except Exception as e:
            logger.error(f"Error reading permanent file {filename}: {e}. Attempting fresh download.")

    try:
        logger.info(f"Fetching fresh symbols from {url}...")
        response = _http_session.get(url, timeout=10)
        response.raise_for_status()
        
        # Save to permanent folder
        with open(perm_path, "wb") as f:
            f.write(response.content)
            
        return pd.read_csv(io.StringIO(response.content.decode('utf-8')))
    except Exception as e:
        logger.error(f"Web fetch failed for {url}: {e}")
        if os.path.exists(perm_path):
            logger.warning(f"Network error. Falling back to permanent list: {filename}")
            return pd.read_csv(perm_path)
        raise

def _extract_symbols(df):
    """Common helper: extract and filter symbols from an NSE CSV DataFrame."""
    symbols = [str(sym).strip() for sym in df['Symbol'].tolist()
               if "DUMMY" not in str(sym).upper() and str(sym).strip()]
    return [f"NSE:{sym}-EQ" for sym in symbols]


def get_nifty50_symbols(live_fetch=False):
    """Fetches Nifty 50 symbols from NSE Archives."""
    filename = "nifty50.csv"
    perm_path = os.path.join(PERMANENT_DIR, filename)
    try:
        df = fetch_with_cache(
            "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
            filename,
            live_fetch=live_fetch
        )
        return _extract_symbols(df)
    except Exception as e:
        logger.error(f"Error fetching Nifty 50: {e}")
        fallback = ["NSE:RELIANCE-EQ", "NSE:TCS-EQ", "NSE:INFY-EQ", "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ"]
        try:
            df_fallback = pd.DataFrame({"Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in fallback]})
            df_fallback.to_csv(perm_path, index=False)
        except Exception:
            pass
        return fallback


def get_nifty200_symbols(live_fetch=False):
    """Fetches Nifty 200 symbols from NSE Archives."""
    filename = "nifty200.csv"
    perm_path = os.path.join(PERMANENT_DIR, filename)
    try:
        df = fetch_with_cache(
            "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
            filename,
            live_fetch=live_fetch
        )
        return _extract_symbols(df)
    except Exception:
        logger.warning("Failing back Nifty 200 to Nifty 500 subset...")
        symbols = get_nifty500_symbols(live_fetch=live_fetch)[:200]
        try:
            df_fallback = pd.DataFrame({"Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in symbols]})
            df_fallback.to_csv(perm_path, index=False)
        except Exception:
            pass
        return symbols


def get_nifty500_symbols(live_fetch=False):
    """Fetches Nifty 500 symbols from NSE Archives."""
    filename = "nifty500.csv"
    perm_path = os.path.join(PERMANENT_DIR, filename)
    try:
        df = fetch_with_cache(
            "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
            filename,
            live_fetch=live_fetch
        )
        return _extract_symbols(df)
    except Exception as e:
        logger.error(f"Fatal error fetching Nifty 500: {e}")
        fallback = ["NSE:RELIANCE-EQ", "NSE:TCS-EQ", "NSE:INFY-EQ", "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ"]
        try:
            df_fallback = pd.DataFrame({"Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in fallback]})
            df_fallback.to_csv(perm_path, index=False)
        except Exception:
            pass
        return fallback


def get_total_cash_segment(live_fetch=False):
    """Fetches ALL NSE-listed equities (~2000+ stocks) from EQUITY_L.csv."""
    filename = "equity_l.csv"
    perm_path = os.path.join(PERMANENT_DIR, filename)
    try:
        df = fetch_with_cache(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            filename,
            live_fetch=live_fetch
        )
        col = 'SYMBOL' if 'SYMBOL' in df.columns else 'Symbol'
        symbols = [str(sym).strip() for sym in df[col].tolist()
                   if "DUMMY" not in str(sym).upper()
                   and str(sym).strip()
                   and not str(sym).startswith('NIFTY')]
        return [f"NSE:{sym}-EQ" for sym in symbols]
    except Exception as e:
        logger.error(f"Error fetching Total Cash Segment: {e}")
        symbols = get_nifty500_symbols(live_fetch=live_fetch)
        try:
            df_fallback = pd.DataFrame({"Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in symbols]})
            df_fallback.to_csv(perm_path, index=False)
        except Exception:
            pass
        return symbols


def get_all_segment(live_fetch=False):
    """Fetches ALL NSE securities (~3200+) from sec_list.csv (EQ, BE, BZ, SM, ST, etc.)."""
    filename = "sec_list.csv"
    perm_path = os.path.join(PERMANENT_DIR, filename)
    try:
        df = fetch_with_cache(
            "https://nsearchives.nseindia.com/content/equities/sec_list.csv",
            filename,
            live_fetch=live_fetch
        )
        col = 'Symbol' if 'Symbol' in df.columns else 'SYMBOL'
        symbols = [str(sym).strip() for sym in df[col].tolist()
                   if "DUMMY" not in str(sym).upper()
                   and str(sym).strip()
                   and not str(sym).startswith('NIFTY')]
        return [f"NSE:{sym}-EQ" for sym in symbols]
    except Exception as e:
        logger.error(f"Error fetching All Segment: {e}")
        symbols = get_total_cash_segment(live_fetch=live_fetch)
        try:
            df_fallback = pd.DataFrame({"Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in symbols]})
            df_fallback.to_csv(perm_path, index=False)
        except Exception:
            pass
        return symbols


def get_index_constituents(index_name, live_fetch=False):
    """Fetches symbols for a specific index by name (with cache)."""
    if index_name == "Nifty 50":
        return get_nifty50_symbols(live_fetch=live_fetch)
    if index_name == "Nifty 200":
        return get_nifty200_symbols(live_fetch=live_fetch)
    if index_name == "Nifty 500":
        return get_nifty500_symbols(live_fetch=live_fetch)
    if index_name == "Total Cash Segment":
        return get_total_cash_segment(live_fetch=live_fetch)
    if index_name == "All Segment":
        return get_all_segment(live_fetch=live_fetch)

    slugs = {
        "Nifty 100": "nifty100",
        "Nifty Next 50": "niftynext50",
        "Nifty Bank": "niftybank",
        "Nifty Auto": "niftyauto",
        "Nifty IT": "niftyit",
        "Nifty PSU Bank": "niftypsubank",
        "Nifty Fin Service": "niftyfinancelist",
        "Nifty Pharma": "niftypharma",
        "Nifty FMCG": "niftyfmcg",
        "Nifty Metal": "niftymetal",
        "Nifty Media": "niftymedia",
        "Nifty Energy": "niftyenergy",
        "Nifty Realty": "niftyrealty",
        "Nifty Healthcare": "niftyhealthcare",
        "Nifty Private Bank": "niftyprivatebank",
        "Nifty Consumption": "niftyconsumption",
        "Nifty Microcap 250": "niftymicrocap250",
        "Nifty Midcap 150": "niftymidcap150",
        "Nifty Midcap 100": "niftymidcap100",
        "Nifty Midcap 50": "niftymidcap50",
        "Nifty Smallcap 250": "niftysmallcap250",
        "Nifty Smallcap 100": "niftysmallcap100",
        "Nifty Smallcap 50": "niftysmallcap50",
        "Nifty Commodities": "niftycommodities",
        "Nifty CPSE": "niftycpse",
        "Nifty Infrastructure": "niftyinfrastructure",
        "Nifty MNC": "niftymnc",
        "Nifty PSE": "niftypse",
        "Nifty Services Sector": "niftyservicesector",
        "Nifty Dividend Opp 50": "niftydividendopportunities50",
        "Nifty Growth Sect 15": "niftygrowthsectors15",
        "Nifty100 Quality 30": "nifty100quality30",
    }

    if index_name in slugs:
        slug = slugs[index_name]
        try:
            url = f"https://archives.nseindia.com/content/indices/ind_{slug}list.csv"
            filename = f"{slug}.csv"
            df = fetch_with_cache(url, filename, live_fetch=live_fetch)
            return _extract_symbols(df)
        except Exception as e:
            logger.warning(f"Could not fetch {index_name}: {e}")

    logger.warning(f"Unknown index '{index_name}', falling back to Nifty 50")
    return get_nifty50_symbols(live_fetch=live_fetch)


def get_all_indices_dict():
    """Returns a dictionary of all supported NSE Indices."""
    return {
        "Nifty 50": "Nifty 50",
        "Nifty Next 50": "Nifty Next 50",
        "Nifty 100": "Nifty 100",
        "Nifty 200": "Nifty 200",
        "Nifty 500": "Nifty 500",
        "All Segment (~3200+)": "All Segment",
        "Total Cash Segment (~2000+)": "Total Cash Segment",
        "Nifty Bank": "Nifty Bank",
        "Nifty Auto": "Nifty Auto",
        "Nifty IT": "Nifty IT",
        "Nifty PSU Bank": "Nifty PSU Bank",
        "Nifty Private Bank": "Nifty Private Bank",
        "Nifty Fin Service": "Nifty Fin Service",
        "Nifty Pharma": "Nifty Pharma",
        "Nifty Healthcare": "Nifty Healthcare",
        "Nifty FMCG": "Nifty FMCG",
        "Nifty Metal": "Nifty Metal",
        "Nifty Media": "Nifty Media",
        "Nifty Energy": "Nifty Energy",
        "Nifty Realty": "Nifty Realty",
        "Nifty Consumption": "Nifty Consumption",
        "Nifty Midcap 50": "Nifty Midcap 50",
        "Nifty Midcap 100": "Nifty Midcap 100",
        "Nifty Midcap 150": "Nifty Midcap 150",
        "Nifty Smallcap 50": "Nifty Smallcap 50",
        "Nifty Smallcap 100": "Nifty Smallcap 100",
        "Nifty Smallcap 250": "Nifty Smallcap 250",
        "Nifty Microcap 250": "Nifty Microcap 250",
        "Nifty Commodities": "Nifty Commodities",
        "Nifty CPSE": "Nifty CPSE",
        "Nifty Infrastructure": "Nifty Infrastructure",
        "Nifty MNC": "Nifty MNC",
        "Nifty PSE": "Nifty PSE",
        "Nifty Services Sector": "Nifty Services Sector",
        "Nifty Dividend Opp 50": "Nifty Dividend Opp 50",
        "Nifty Growth Sect 15": "Nifty Growth Sect 15",
        "Nifty100 Quality 30": "Nifty100 Quality 30",
    }


# ============================================================
# SYMBOL NORMALIZATION
# ============================================================

def normalize_symbol(symbol):
    """Normalizes symbol to internal format (NSE:SYMBOL-EQ) or (NSE:INDEX-INDEX)."""
    symbol = symbol.strip().upper()

    index_map = {
        "^NSEI": "NSE:NIFTY50-INDEX",
        "NIFTY": "NSE:NIFTY50-INDEX",
        "^NSEBANK": "NSE:NIFTYBANK-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
        "NIFTY50": "NSE:NIFTY50-INDEX",
        "NIFTYBANK": "NSE:NIFTYBANK-INDEX"
    }
    if symbol in index_map:
        return index_map[symbol]

    if ":" in symbol and "-" in symbol:
        return symbol

    symbol = symbol.replace(".NS", "").replace(".BO", "")
    return f"NSE:{symbol}-EQ"


def nse_to_yahoo(nse_symbol):
    """Convert NSE format (NSE:RELIANCE-EQ) to Yahoo Finance format (RELIANCE.NS)."""
    sym = nse_symbol.upper()
    # Handle index symbols
    if "NIFTY50" in sym or "NSEI" in sym:
        return "^NSEI"
    if "NIFTYBANK" in sym or "NSEBANK" in sym:
        return "^NSEBANK"
    # Handle equity symbols: NSE:RELIANCE-EQ -> RELIANCE.NS
    if ":" in sym:
        sym = sym.split(":")[1]
    sym = sym.replace("-EQ", "").replace("-INDEX", "")
    # Apply symbol aliases for renamed stocks (e.g. ZOMATO -> ETERNAL)
    if sym in SYMBOL_ALIASES:
        sym = SYMBOL_ALIASES[sym]
    return f"{sym}.NS"


_YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
_YF_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_YF_TIMEOUT = 15


def _yf_fetch_chart(yf_symbol, interval='1h', range_str='60d'):
    """Fetch raw Yahoo Finance chart data via direct API."""
    url = f"{_YF_BASE}/{yf_symbol}?interval={interval}&range={range_str}"
    req = urllib.request.Request(url, headers={"User-Agent": _YF_UA})
    try:
        with urllib.request.urlopen(req, timeout=_YF_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["chart"]["result"][0]
    except Exception as e:
        logger.debug(f"Yahoo Finance API error for {yf_symbol}: {e}")
        return None


def fetch_data_yfinance(symbol, interval='1d'):
    """Fetch OHLCV data from Yahoo Finance direct API (single HTTP request per symbol)."""
    try:
        yf_symbol = nse_to_yahoo(symbol)

        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m',
            '30m': '30m', '60m': '60m', '1h': '1h',
            '1d': '1d', 'D': '1d', 'W': '1wk', 'M': '1mo',
            '1wk': '1wk', '1mo': '1mo'
        }
        yf_interval = interval_map.get(interval, '1d')

        if yf_interval == '1m':
            range_str = '5d'
        elif yf_interval in ['5m', '15m', '30m', '60m', '1h']:
            range_str = '60d'
        elif yf_interval == '1wk':
            range_str = '5y'
        elif yf_interval == '1mo':
            range_str = '10y'
        else:
            range_str = '2y'

        chart_result = _yf_fetch_chart(yf_symbol, interval=yf_interval, range_str=range_str)

        if chart_result is None:
            return pd.DataFrame()

        timestamps = chart_result.get("timestamp", [])
        indicators = chart_result.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps:
            return pd.DataFrame()

        df = pd.DataFrame({
            'open': indicators.get('open', []),
            'high': indicators.get('high', []),
            'low': indicators.get('low', []),
            'close': indicators.get('close', []),
            'volume': indicators.get('volume', []),
        })

        df.index = pd.to_datetime(timestamps, unit='s')
        df.index = df.index.tz_localize('UTC').tz_convert(IST)

        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # Forward-fill volume gaps (e.g. pre/post market NaN bars)
        # then drop rows that still have 0 or NaN volume (halted / bad data)
        df['volume'] = df['volume'].ffill().fillna(0)
        df = df[df['volume'] > 0].copy()

        # Drop rows where price data is missing
        df = df.dropna(subset=['open', 'high', 'low', 'close'])

        if df.empty:
            return pd.DataFrame()

        df['volume'] = df['volume'].astype(int)

        return df

    except Exception as e:
        logger.warning(f"Yahoo Finance error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_data_yf_lib(symbol, interval='1d'):
    """Fetch OHLCV data using yfinance library (multiple HTTP requests per symbol)."""
    try:
        yf_symbol = nse_to_yahoo(symbol)

        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m',
            '30m': '30m', '60m': '60m', '1h': '1h',
            '1d': '1d', 'D': '1d', 'W': '1wk', 'M': '1mo',
            '1wk': '1wk', '1mo': '1mo'
        }
        yf_interval = interval_map.get(interval, '1d')

        if yf_interval == '1m':
            period = '5d'
        elif yf_interval in ['5m', '15m', '30m', '60m', '1h']:
            period = '60d'
        elif yf_interval == '1wk':
            period = '5y'
        elif yf_interval == '1mo':
            period = '10y'
        else:
            period = '2y'

        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=yf_interval)

        if df.empty:
            return pd.DataFrame()

        df.columns = [c.lower() for c in df.columns]
        df = df[['open', 'high', 'low', 'close', 'volume']].copy()

        if df.index.tz is not None:
            if str(df.index.tz) != 'Asia/Kolkata':
                df.index = df.index.tz_convert(IST)
        else:
            df.index = df.index.tz_localize('UTC').tz_convert(IST)

        # Forward-fill volume gaps then drop zero/NaN volume bars
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').ffill().fillna(0)
        df = df[df['volume'] > 0].copy()
        df = df.dropna(subset=['open', 'high', 'low', 'close'])

        if df.empty:
            return pd.DataFrame()

        df['volume'] = df['volume'].astype(int)

        return df

    except Exception as e:
        logger.warning(f"yfinance library error for {symbol}: {e}")
        return pd.DataFrame()


# ============================================================
# DATA SOURCE MANAGEMENT
# ============================================================

_DATA_SOURCE_MAP = {
    "auto": "yahoo",
    "yahoo": "yahoo",
    "yfapi": "yahoo",
    "yfinance": "yfinance",
    "yflib": "yfinance",
}

_active_data_source = "yahoo"


def set_data_source(source):
    """Set the active data source. Called from Streamlit UI or CLI."""
    global _active_data_source
    ds = _DATA_SOURCE_MAP.get(source.lower(), "yahoo")
    _active_data_source = ds
    logger.info(f"Data source set to: {ds}")


def get_data_source():
    """Get the current active data source."""
    return _active_data_source


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_data(symbol, interval='1d', data_source=None, period=None, retries=3):
    """
    Fetches historical OHLCV data.
    Checks disk cache first, then tries primary source, then falls back.
    """
    symbol = normalize_symbol(symbol)

    ds = data_source or _active_data_source
    ds = _DATA_SOURCE_MAP.get(ds.lower() if ds else "yahoo", "yahoo")

    # Check disk cache first — avoids redundant network requests
    res_map = {
        '1m': '1', '5m': '5', '15m': '15', '30m': '30', '60m': '60', '1h': '60',
        '1d': 'D', 'D': 'D', 'W': 'W', 'M': 'M', '1wk': 'W', '1mo': 'M'
    }
    resolution = res_map.get(interval, 'D')

    if interval in ['1wk', 'W']:
        days_lookback = 365 * 5
    elif interval in ['1mo', 'M']:
        days_lookback = 365 * 10
    elif interval in ['5m', '15m', '30m', '60m', '1h']:
        days_lookback = 60
    elif interval == '1m':
        days_lookback = 5
    else:
        days_lookback = 730

    range_to = datetime.now().strftime("%Y-%m-%d")
    range_from = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")

    cached = _get_ohlcv_cache(symbol, resolution, range_from, range_to)
    if cached is not None:
        return cached

    # Try primary source
    if ds == "yahoo":
        df = fetch_data_yfinance(symbol, interval=interval)
    else:
        df = fetch_data_yf_lib(symbol, interval=interval)

    if not df.empty:
        _set_ohlcv_cache(symbol, resolution, range_from, range_to, df)
        return df

    # Fallback
    if ds == "yahoo":
        logger.info(f"Yahoo direct failed for {symbol}, trying yfinance library...")
        df = fetch_data_yf_lib(symbol, interval=interval)
    else:
        logger.info(f"yfinance library failed for {symbol}, trying Yahoo direct API...")
        df = fetch_data_yfinance(symbol, interval=interval)

    if not df.empty:
        _set_ohlcv_cache(symbol, resolution, range_from, range_to, df)
        return df

    return pd.DataFrame()


def fetch_data_batch(symbols, interval='1d', max_workers=4, progress_callback=None, phase_label=""):
    """Batch fetch OHLCV data with rate limiting to avoid Yahoo Finance blocks."""
    t0 = time.time()
    results = {}
    total = len(symbols)
    ds = _active_data_source
    logger.info(f"Batch fetch: {total} symbols ({ds}, {max_workers} workers)")

    def _fetch_one(sym):
        time.sleep(0.15)  # Delay to prevent hitting rate limits
        df = fetch_data(sym, interval=interval, data_source=ds)
        return sym, df

    done_count = 0
    unique_count = 0
    failed_symbols = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(futures):
            try:
                sym, df = future.result(timeout=60)
                if df is not None and not df.empty:
                    # Store under raw, normalised, and Yahoo key for seamless lookup
                    norm_sym = normalize_symbol(sym)
                    y_sym = nse_to_yahoo(sym)
                    results[sym] = df
                    results[norm_sym] = df
                    results[y_sym] = df
                    unique_count += 1
                else:
                    failed_symbols.append(sym)
            except Exception as e:
                sym = futures[future]
                failed_symbols.append(sym)
                logger.warning(f"Failed to fetch {sym}: {e}")
            done_count += 1
            if progress_callback:
                progress_callback(done_count, total)

    elapsed = time.time() - t0
    logger.info(f"Batch complete: {unique_count} unique symbols in {elapsed:.1f}s")
    if failed_symbols:
        logger.warning(
            f"Failed symbols ({len(failed_symbols)}): "
            f"{', '.join(failed_symbols[:20])}"
            f"{'...' if len(failed_symbols) > 20 else ''}"
        )
    return results


def is_market_open():
    """Check if NSE market is currently open (Mon-Fri, 9:15-15:30 IST)."""
    now = get_now_ist()
    if now.weekday() > 4:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def clear_ohlcv_cache():
    """Clears all OHLCV cache files."""
    count = 0
    for f in os.listdir(OHLCV_CACHE_DIR):
        if f.endswith(('.parquet', '.pkl')):
            try:
                os.remove(os.path.join(OHLCV_CACHE_DIR, f))
                count += 1
            except Exception:
                pass
    logger.info(f"Cleared {count} OHLCV cache files")
    return count


_categories_loaded = False
_symbol_to_categories = {}

def load_all_categories():
    global _categories_loaded, _symbol_to_categories
    if _categories_loaded:
        return
    
    _symbol_to_categories = {}
    
    if not os.path.exists(PERMANENT_DIR):
        _categories_loaded = True
        return
        
    for filename in os.listdir(PERMANENT_DIR):
        if not filename.endswith('.csv'):
            continue
        
        # Skip segment catalogs and custom lists
        if filename in ['equity_l.csv', 'sec_list.csv', 'custom_list.csv']:
            continue
            
        name_clean = filename.replace('.csv', '').lower()
        
        # Mapping to user-friendly label formats
        if name_clean == 'nifty50':
            cat_label = '50'
        elif name_clean == 'niftynext50':
            cat_label = 'Next 50'
        elif name_clean == 'nifty100':
            cat_label = '100'
        elif name_clean == 'nifty200':
            cat_label = '200'
        elif name_clean == 'nifty500':
            cat_label = 'nse500'
        elif name_clean == 'niftymidcap150':
            cat_label = 'mid'
        elif name_clean == 'niftysmallcap250':
            cat_label = 'small'
        else:
            cat_label = name_clean.replace('nifty', '').replace('list', '').capitalize()
            if not cat_label:
                cat_label = name_clean.capitalize()
                
        file_path = os.path.join(PERMANENT_DIR, filename)
        try:
            df = pd.read_csv(file_path)
            col = 'Symbol' if 'Symbol' in df.columns else ('SYMBOL' if 'SYMBOL' in df.columns else None)
            if col is None and not df.empty:
                col = df.columns[0]
                
            if col is not None:
                symbols = [str(s).strip().upper() for s in df[col].tolist() if pd.notna(s)]
                for sym in symbols:
                    clean_sym = sym.replace("NSE:", "").replace("-EQ", "").replace(".NS", "").replace("-INDEX", "").strip().upper()
                    if clean_sym not in _symbol_to_categories:
                        _symbol_to_categories[clean_sym] = []
                    if cat_label not in _symbol_to_categories[clean_sym]:
                        _symbol_to_categories[clean_sym].append(cat_label)
        except Exception as e:
            logger.debug(f"Could not load category file {filename}: {e}")
            
    _categories_loaded = True

def get_stock_categories_string(symbol):
    load_all_categories()
    clean = symbol.replace("NSE:", "").replace("-EQ", "").replace(".NS", "").replace("-INDEX", "").strip().upper()
    cats = _symbol_to_categories.get(clean, [])
    
    # Prioritized sorting for standard index prefixes, followed by alphabetical order
    priorities = {'50': 0, 'Next 50': 1, '100': 2, '200': 3, 'nse500': 4, 'mid': 5, 'small': 6}
    sorted_cats = sorted(cats, key=lambda c: (priorities.get(c, 99), c))
    
    return ", ".join(sorted_cats) if sorted_cats else "Other"


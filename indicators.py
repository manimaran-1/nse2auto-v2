import pandas as pd
import numpy as np

def calculate_ema(df, length):
    """
    Calculate Exponential Moving Average.
    """
    return df['close'].ewm(span=length, adjust=False).mean()

def calculate_stoch_rsi(df, length=14, rsi_length=14, k=3, d=3):
    """
    Calculate Stochastic RSI perfectly matching Wilder's logic.
    """
    # 1. Calculate traditional RSI
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    
    alpha = 1 / rsi_length
    roll_up = up.ewm(alpha=alpha, adjust=False).mean()
    roll_down = down.ewm(alpha=alpha, adjust=False).mean()
    
    rs = roll_up / roll_down
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # 2. Calculate Stochastic of RSI
    rsi_min = rsi.rolling(window=length).min()
    rsi_max = rsi.rolling(window=length).max()
    
    # Avoid division by zero
    stoch_rsi = 100 * (rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)
    stoch_rsi = stoch_rsi.fillna(0)
    
    # 3. Smooth for %K
    stoch_rsi_k = stoch_rsi.rolling(window=k).mean()
    
    return stoch_rsi_k

def calculate_rsi(df, length=14):
    """
    Calculate Standard RSI matching TradingView/Wilder's logic.
    """
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    
    alpha = 1 / length
    roll_up = up.ewm(alpha=alpha, adjust=False).mean()
    roll_down = down.ewm(alpha=alpha, adjust=False).mean()
    
    rs = roll_up / roll_down
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_bb_width(df, length=20, std_dev=2):
    """
    Calculate Bollinger Band Width for squeeze detection.
    """
    sma = df['close'].rolling(window=length).mean()
    std = df['close'].rolling(window=length).std()
    upper_bb = sma + (std_dev * std)
    lower_bb = sma - (std_dev * std)
    bb_width = (upper_bb - lower_bb) / sma.replace(0, np.nan)
    return bb_width.fillna(0)

def calculate_smi(df, length=10, smooth=3):
    """
    Calculate Stochastic Momentum Index matching Pine Script.
    """
    hh = df['high'].rolling(window=length).max()
    ll = df['low'].rolling(window=length).min()
    
    diff = hh - ll
    rdiff = df['close'] - (hh + ll) / 2
    
    avg_rdiff = rdiff.ewm(span=smooth, adjust=False).mean().ewm(span=smooth, adjust=False).mean()
    avg_diff = diff.ewm(span=smooth, adjust=False).mean().ewm(span=smooth, adjust=False).mean()
    
    smi = np.where(avg_diff != 0, 100 * avg_rdiff / (avg_diff / 2), 0)
    
    return pd.Series(smi.flatten(), index=df.index)

def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Calculate MACD Line and Histogram.
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_vwap(df):
    """
    Calculate Intra-day Volume Weighted Average Price (VWAP).
    Resets at the start of each session.
    """
    # Group by date to handle session resets
    curr_df = df.copy()
    curr_df['Date'] = curr_df.index.date
    curr_df['Typical_Price'] = (curr_df['high'] + curr_df['low'] + curr_df['close']) / 3
    curr_df['TP_Vol'] = curr_df['Typical_Price'] * curr_df['volume']
    
    # Calculate cumulative sums within each date group
    grouped = curr_df.groupby('Date')
    cum_tp_vol = grouped['TP_Vol'].cumsum()
    cum_vol = grouped['volume'].cumsum()
    
    vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
    return vwap.fillna(curr_df['close'])

def calculate_adx(df, length=14):
    """
    Calculate ADX (Average Directional Index) to measure trend strength.
    Uses Wilder's smoothing.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high.diff()
    down_move = low.diff().mul(-1)
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Smooth with Wilder's (using RMA/SMMA alpha)
    alpha = 1 / length
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    
    return adx.fillna(0)

def calculate_atr(df, length=14):
    """
    Calculate ATR (Average True Range) using Wilder's smoothing.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    alpha = 1 / length
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    return atr.fillna(0)

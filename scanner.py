import os
import pandas as pd
import indicators
import data_loader
import config
import pytz
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

def check_conditions(df, symbol, nifty_df=None):
    """
    Checks the defined strategy criteria against the dataframe.
    Returns a list of matching results.
    """
    strat = config.STRATEGY_CONFIG
    
    if df.empty or len(df) < 50:
        return []
        
    # Calculate Indicators
    close = df['close']
    volume = df['volume']
    
    # EMA check - Ensure 5, 9, 21, 50 are available for both Selection and Signature
    display_ema_lengths = strat.get("EMA", [5, 9, 21])
    required_emas = set(display_ema_lengths) | {5, 9, 21, 50}
    emas = {length: indicators.calculate_ema(df, length) for length in required_emas}
    
    # Oscillators/Momentum
    stoch_rsi_k = indicators.calculate_stoch_rsi(df, **strat.get("STOCH_RSI", {}))
    smi = indicators.calculate_smi(df, **strat.get("SMI", {}))
    rsi = indicators.calculate_rsi(df)
    macd_line, signal_line, macd_hist = indicators.calculate_macd(df, **strat.get("MACD", {}))
    bb_width = indicators.calculate_bb_width(df)
    vwap = indicators.calculate_vwap(df)
    adx = indicators.calculate_adx(df)
    atr = indicators.calculate_atr(df)
    
    results = []
    
    # Intraday heuristic
    is_intraday = False
    if len(df) > 1:
        time_diff = df.index[-1] - df.index[-2]
        if time_diff < pd.Timedelta(days=1):
            is_intraday = True

    indices_to_check = []
    if is_intraday:
        now_ist = data_loader.get_now_ist()
        today_date = now_ist.date()
        
        candidates = df.index[-75:] 
        today_indices = [idx for idx in candidates if idx.date() == today_date]
        
        if today_indices:
            indices_to_check = today_indices
        else:
            # Fallback to last available trading day
            last_date = df.index[-1].date()
            indices_to_check = [idx for idx in candidates if idx.date() == last_date]
    else:
        # Check only the latest completed candle
        indices_to_check = [df.index[-1]]
    
    day_open_price = None
    if is_intraday and not df.empty:
        # Find first candle of the most recent day in the df
        last_date = df.index[-1].date()
        today_data = df[df.index.date == last_date]
        if not today_data.empty:
            day_open_price = today_data.iloc[0]['open']

    # Avg Volume for RVOL
    avg_vol_20 = volume.rolling(window=20).mean()

    # Volatility: standard deviation of daily returns in % over a 20-period rolling window
    daily_returns_pct = close.pct_change() * 100
    rolling_vol = daily_returns_pct.rolling(window=20).std()

    # Pre-calculate Relative Strength if Nifty is provided
    nifty_changes = pd.Series(0, index=df.index)
    if nifty_df is not None and not nifty_df.empty:
        common_idx = df.index.intersection(nifty_df.index)
        if len(common_idx) > 5:
            nifty_c = nifty_df['close'].reindex(df.index).ffill()
            # 5-period performance comparison
            nifty_5_perf = (nifty_c / nifty_c.shift(5) - 1) * 100
            nifty_changes = nifty_5_perf

    for idx in indices_to_check:
        try:
            pos = df.index.get_loc(idx)
            if pos < 5: continue # Need history for 5-period RS
            
            c = close.iloc[pos]
            v = volume.iloc[pos]

            # Skip zero-volume candles (pre/post market, halted trading)
            if pd.isna(v) or v <= 0:
                continue

            k = stoch_rsi_k.iloc[pos]
            s = smi.iloc[pos]
            m = macd_line.iloc[pos]
            mh = macd_hist.iloc[pos]
            r = rsi.iloc[pos]
            bw = bb_width.iloc[pos]
            vw = vwap.iloc[pos]
            ax = adx.iloc[pos]
            avg_v = avg_vol_20.iloc[pos]
            atr_val = atr.iloc[pos]

            # Guard: need a valid rolling average volume or ATR
            if pd.isna(avg_v) or avg_v <= 0:
                avg_v = float(v)  # fallback: use current bar's own volume
            if pd.isna(atr_val) or atr_val <= 0:
                atr_val = c * 0.02  # fallback: 2% of price

            
            # Volatility calculation
            vol = rolling_vol.iloc[pos]
            if pd.isna(vol) or vol <= 0:
                vol = 1.0
            
            # --- Tier 1: Base Selection (The Ticket to Entry) ---
            # 1. EMAs: Price > 5, 9, 21
            price_above_entry_emas = c > emas[5].iloc[pos] and c > emas[9].iloc[pos] and c > emas[21].iloc[pos]
            # 2. Oscillators: Stoch RSI K > 70, SMI > 30
            stoch_rsi_ok = k > 70
            smi_ok = s > 30
            # 3. MACD: MACD Line > 0.75
            macd_ok = m > 0.75
            
            # NEW INTRADAY ANCHOR: Price > VWAP
            vwap_ok = c > vw
            
            if not (price_above_entry_emas and stoch_rsi_ok and smi_ok and macd_ok and vwap_ok):
                continue
 
            # --- Tier 2: Momentum Signature (The Gold Badge) ---
            # 1. Relative Performance (Stock vs Nifty)
            stock_5_perf = (c / close.iloc[pos-5] - 1) * 100
            relative_strength = stock_5_perf - nifty_changes.iloc[pos]
            
            # Volatility-adjusted RS: use standard deviation with a 0.5% floor to prevent division by near-zero
            vol_adj_rs = relative_strength / max(vol, 0.5)
            
            # 2. Resolve current date first (needed by ORB30 fallback and prev-day logic)
            current_date = idx.date()

            # 3. ORB30 (Opening Range Breakout - High of first 30 mins)
            orb30_high = 0
            if is_intraday:
                # Get data for current trading day up to 9:45 AM
                today_start = idx.replace(hour=9, minute=15, second=0, microsecond=0)
                today_orb_end = idx.replace(hour=9, minute=45, second=0, microsecond=0)
                orb_data = df.loc[today_start:today_orb_end]
                if not orb_data.empty:
                    orb30_high = orb_data['high'].max()
                else:
                    # Fallback: use high of the first candle of the current day
                    day_data = df[df.index.date == current_date]
                    if not day_data.empty:
                        orb30_high = day_data.iloc[0]['high']

            # 4. Find Previous Trading Day Stats
            prev_day_data = df[df.index.date < current_date]
            
            if not prev_day_data.empty:
                prev_day_high = prev_day_data['high'].max() 
                prev_day_last_bbw = bb_width.loc[prev_day_data.index[-1]]
            else:
                prev_day_high = df['high'].iloc[pos-1]
                prev_day_last_bbw = bb_width.iloc[pos-1]
 
            # 1. Strict Trend: Price > EMA 9 > 21 > 50
            ema_alignment = False
            e9 = emas[9].iloc[pos]
            e21 = emas[21].iloc[pos]
            e50 = emas[50].iloc[pos]
            if c > e9 > e21 > e50:
                ema_alignment = True
            
            # 2. Momentum Confluence: RSI > 60 AND MACD Hist > 0
            momentum_confluence = (r > 60 and mh > 0)
            
            # 3. Launchpad & Strength: Prev Day Squeeze AND ADX > 20
            is_launchpad = (prev_day_last_bbw <= 0.05) and (ax > 20)
            
            # 4. Trigger: Vol > 2x Avg AND Current Price > Prev Day High AND Relative Strength > 0 
            #    AND Price > ORB30 High
            is_triggered = (v > avg_v * 2) and (c > prev_day_high) and (relative_strength > -0.1)
            if orb30_high > 0:
                is_triggered = is_triggered and (c > orb30_high)
            
            momentum_signature = False
            if ema_alignment and momentum_confluence and is_launchpad and is_triggered:
                momentum_signature = True
            
            clean_symbol = symbol.replace("NSE:", "").replace("-EQ", "").replace(".NS", "").replace("-INDEX", "")
            rvol = round(float(v) / float(avg_v), 2) if avg_v > 0 else 1.0
            res = {
                'Stock Name': clean_symbol,
                'LTP': round(c, 2),
                'Day Open': round(day_open_price, 2) if day_open_price else round(c, 2),
                'Signal Time': idx.strftime('%d-%m-%Y %H:%M'),
                'Volume': int(v),
                'RVOL': rvol,
                'Stoch RSI K': round(k, 2),
                'RSI': round(r, 2),
                'SMI': round(s, 2),
                'MACD': round(m, 2),
                'MACD_Hist': round(mh, 2),
                'BBW': round(bw, 3),
                'VWAP': round(vw, 2),
                'ADX': round(ax, 1),
                'Rel Strength': round(relative_strength, 2),
                'Volatility': round(vol, 2),
                'Vol-Adjusted RS': round(vol_adj_rs, 2),
                'ATR': round(atr_val, 2),
                'is_momentum_signature': momentum_signature,
                'is_squeeze': is_launchpad
            }
            
            for length in display_ema_lengths:
                res[f'EMA{length}'] = round(emas[length].iloc[pos], 2)
            
            results.append(res)
            
        except Exception as e:
            logger.debug(f"Error checking index {idx} for {symbol}: {e}")
            continue
            
    return results

def scan_symbol(symbol, interval, nifty_df=None):
    """
    Fallback worker function to fetch and scan a single symbol.
    """
    df = data_loader.fetch_data(symbol, interval=interval)
    return check_conditions(df, symbol, nifty_df=nifty_df)

def scan_market(symbols, interval='1d', progress_callback=None):
    """
    Executes a market scan by pre-fetching symbols in a batch and processing technical indicators.
    """
    all_results = []
    
    # Pre-fetch Nifty 50 for Relative Strength calculation
    nifty_df = None
    try:
        logger.info("Fetching Nifty 50 benchmark data...")
        nifty_df = data_loader.fetch_data("^NSEI", interval=interval)
    except Exception as e:
        logger.warning(f"Could not fetch Nifty 50 data for RS calculation: {e}")

    logger.info("Pre-fetching market data in batches...")
    # Pre-fetch data in batch using data_loader.fetch_data_batch
    stock_data = data_loader.fetch_data_batch(
        symbols, 
        interval=interval, 
        max_workers=4, 
        progress_callback=progress_callback
    )

    logger.info("Processing scanned symbols...")
    for symbol in symbols:
        try:
            norm_sym = data_loader.normalize_symbol(symbol)
            df = stock_data.get(norm_sym)
            if df is None or df.empty:
                df = stock_data.get(symbol)
                if df is None or df.empty:
                    df = stock_data.get(data_loader.nse_to_yahoo(symbol))
            
            if df is not None and not df.empty:
                res_list = check_conditions(df, symbol, nifty_df=nifty_df)
                if res_list:
                    all_results.extend(res_list)
        except Exception as e:
            logger.debug(f"Error processing {symbol}: {e}")

    return pd.DataFrame(all_results)

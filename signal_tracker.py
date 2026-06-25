import os
import json
import logging
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
import data_loader

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')

TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "signal_tracker.json")

def load_tracker():
    """Loads the tracker state from cache/signal_tracker.json."""
    if not os.path.exists(TRACKER_FILE):
        os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
        return {"active": [], "completed": []}
    
    try:
        with open(TRACKER_FILE, "r") as f:
            state = json.load(f)
        if "active" not in state:
            state["active"] = []
        if "completed" not in state:
            state["completed"] = []
        return state
    except Exception as e:
        logger.error(f"Error loading tracker: {e}")
        return {"active": [], "completed": []}

def save_tracker(state):
    """Saves the tracker state to cache/signal_tracker.json."""
    try:
        os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
        with open(TRACKER_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving tracker: {e}")

def reset_tracker():
    """Resets the tracker state to empty."""
    save_tracker({"active": [], "completed": []})
    logger.info("Signal tracker state has been reset.")

def parse_date(date_str):
    """Parses date string with fallback formats."""
    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.now()

def fetch_current_price(symbol, timeframe='1d'):
    """Fetches the current/latest close price for the symbol from data_loader."""
    try:
        # Construct full symbol expected by data_loader
        full_symbol = data_loader.normalize_symbol(symbol)
        df = data_loader.fetch_data(full_symbol, interval=timeframe)
        if not df.empty and 'close' in df.columns:
            return float(df['close'].iloc[-1])
    except Exception as e:
        logger.error(f"Error fetching current price for {symbol}: {e}")
    return None

def compute_scores_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """Computes Classic and Enhanced scores for a results DataFrame if not already present."""
    df = df.copy()
    if df.empty:
        return df
    
    if 'Classic_Score' in df.columns and 'Enhanced_Score' in df.columns:
        return df

    if "Day Open" not in df.columns or "LTP" not in df.columns:
        df["Classic_Score"] = 0.0
        df["Enhanced_Score"] = 0.0
        return df

    df["Change_Pct"] = ((df["LTP"] - df["Day Open"]) / df["Day Open"]) * 100

    if "ATR" not in df.columns:
        df["ATR"] = df["LTP"] * 0.02
    else:
        df["ATR"] = df["ATR"].fillna(df["LTP"] * 0.02)

    # Classic 3-Factor
    smi_col = df["SMI"] if "SMI" in df.columns else pd.Series(0.0, index=df.index)
    macd_col = df["MACD"] if "MACD" in df.columns else pd.Series(0.0, index=df.index)
    df["Classic_Score"] = (
        df["Change_Pct"].clip(0, 5) / 5 * 40
        + smi_col.clip(0, 100) / 100 * 30
        + macd_col.clip(0, 5) / 5 * 30
    ).fillna(0).clip(0, 100)

    # Refined V3 Enhanced 5-Factor
    atr_pct = ((df["ATR"] / df["Day Open"]) * 100).clip(lower=0.5)
    change_norm = df["Change_Pct"] / (atr_pct * 1.5)
    change_5f = change_norm.clip(-0.5, 1.0) * 30

    smi_val = df["SMI"] if "SMI" in df.columns else pd.Series(0.0, index=df.index)
    smi_5f = np.where(
        (smi_val >= 40) & (smi_val < 80), 
        20.0, 
        np.where(smi_val >= 80, 10.0, 0.0)
    )

    macd_val = df["MACD"] if "MACD" in df.columns else pd.Series(0.0, index=df.index)
    macd_norm = macd_val / (df["ATR"] * 3.0)
    macd_5f = macd_norm.clip(0, 1.0) * 20

    rvol_val = df["RVOL"] if "RVOL" in df.columns else pd.Series(1.0, index=df.index)
    rvol_5f = np.where(
        rvol_val < 1.0,
        ((rvol_val - 1.0) * 10.0).clip(lower=-10.0),
        np.where(
            rvol_val < 1.5,
            ((rvol_val - 1.0) / 0.5) * 15.0,
            15.0 + (rvol_val - 1.5) * 2.0
        )
    )

    rs_val = df["Rel Strength"] if "Rel Strength" in df.columns else pd.Series(0.0, index=df.index)
    vol_val = df["Volatility"] if "Volatility" in df.columns else pd.Series(1.0, index=df.index)
    vol_effective = vol_val.clip(lower=0.5)
    rs_5f = (rs_val / (vol_effective * 2.0)).clip(0, 1.0) * 15

    df["Enhanced_Score"] = (
        change_5f + smi_5f + macd_5f + rvol_5f + rs_5f
    ).fillna(0).clip(0, 100)

    return df

def update_tracker(results_df, universe, timeframe):
    """
    Updates the signal tracker with the current scan results.
    Identifies new entries, updates trailing highest/lowest prices for active positions,
    and identifies exited signals (dropped out from criteria) to log backtest results.
    
    Returns:
        tuple: (new_entries, new_exits) as list of dictionaries.
    """
    now_ist = datetime.now(IST)
    now_str = now_ist.strftime("%d-%m-%Y %H:%M")
    
    state = load_tracker()
    
    # Pre-process current results to ensure scores are calculated
    processed_df = compute_scores_if_needed(results_df)
    
    # Dedup current scan symbols (highest volume/first appearance)
    if not processed_df.empty:
        processed_df = processed_df.sort_values(by="Volume", ascending=False).drop_duplicates(subset="Stock Name")
        current_symbols = set(processed_df["Stock Name"].tolist())
        current_data = {row["Stock Name"]: row for _, row in processed_df.iterrows()}
    else:
        current_symbols = set()
        current_data = {}
        
    # Segment active signals: separating this universe/timeframe from others
    other_active = []
    this_active = []
    
    for sig in state["active"]:
        if sig.get("universe") == universe and sig.get("timeframe") == timeframe:
            this_active.append(sig)
        else:
            other_active.append(sig)
            
    this_active_map = {sig["symbol"]: sig for sig in this_active}
    
    new_entries = []
    new_exits = []
    updated_active = []
    
    # 1. Process New Entries & Still-Active signals
    for symbol in current_symbols:
        row = current_data[symbol]
        ltp = float(row["LTP"])
        c_score = float(row.get("Classic_Score", 0.0))
        e_score = float(row.get("Enhanced_Score", 0.0))
        sig_time = row.get("Signal Time", now_str)
        
        if symbol in this_active_map:
            # Update existing active signal
            sig = this_active_map[symbol]
            sig["last_price"] = ltp
            sig["highest_price"] = max(sig.get("highest_price", ltp), ltp)
            sig["lowest_price"] = min(sig.get("lowest_price", ltp), ltp)
            sig["last_updated"] = now_str
            sig["score_3_factor"] = c_score
            sig["score_5_factor"] = e_score
            updated_active.append(sig)
        else:
            # Create a new active signal
            new_sig = {
                "symbol": symbol,
                "universe": universe,
                "timeframe": timeframe,
                "entry_date": sig_time,
                "entry_price": ltp,
                "highest_price": ltp,
                "lowest_price": ltp,
                "last_price": ltp,
                "last_updated": now_str,
                "score_3_factor": c_score,
                "score_5_factor": e_score
            }
            new_entries.append(new_sig)
            updated_active.append(new_sig)
            
    # 2. Process Exits (signals in active that are NOT in current scan)
    for symbol, sig in this_active_map.items():
        if symbol not in current_symbols:
            # Stock has dropped out of criteria! Fetch current price to lock exit
            exit_price = fetch_current_price(symbol, timeframe)
            if exit_price is None:
                exit_price = sig["last_price"]
                
            entry_price = sig["entry_price"]
            highest_price = max(sig.get("highest_price", exit_price), exit_price)
            lowest_price = min(sig.get("lowest_price", exit_price), exit_price)
            
            # Backtest Calculations
            return_pct = ((exit_price - entry_price) / entry_price) * 100
            max_runup_pct = ((highest_price - entry_price) / entry_price) * 100
            max_drawdown_pct = ((lowest_price - entry_price) / entry_price) * 100
            
            # Duration calculation
            entry_dt = parse_date(sig["entry_date"])
            exit_dt = now_ist.replace(tzinfo=None)
            duration_days = max(0.0, (exit_dt - entry_dt).total_seconds() / 86400.0)
            
            completed_sig = {
                "symbol": symbol,
                "universe": universe,
                "timeframe": timeframe,
                "entry_date": sig["entry_date"],
                "exit_date": now_str,
                "entry_price": entry_price,
                "exit_price": round(exit_price, 2),
                "highest_price": round(highest_price, 2),
                "lowest_price": round(lowest_price, 2),
                "return_pct": round(return_pct, 2),
                "max_runup_pct": round(max_runup_pct, 2),
                "max_drawdown_pct": round(max_drawdown_pct, 2),
                "duration_days": round(duration_days, 2),
                "score_3_factor": sig.get("score_3_factor", 0.0),
                "score_5_factor": sig.get("score_5_factor", 0.0)
            }
            new_exits.append(completed_sig)
            state["completed"].append(completed_sig)
            
    # Combine active signals
    state["active"] = other_active + updated_active
    save_tracker(state)
    
    return new_entries, new_exits

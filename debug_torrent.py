import os
import pandas as pd
import indicators
import data_loader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_macd_crossover_debug(symbol):
    df = data_loader.fetch_data(symbol, period='6mo', interval='1d')
    if df.empty or len(df) < 50:
        print(f"Empty data for {symbol}")
        return None
    
    macd_line, signal_line, _ = indicators.calculate_macd(df)
    
    print(f"\nDebug for {symbol}:")
    print(f"LTP: {df['close'].iloc[-1]}")
    
    for i in range(1, 11):
        curr_pos = -i
        prev_pos = -i - 1
        m_curr = macd_line.iloc[curr_pos]
        s_curr = signal_line.iloc[curr_pos]
        m_prev = macd_line.iloc[prev_pos]
        s_prev = signal_line.iloc[prev_pos]
        
        cross = "BULISH CROSS" if (m_prev <= s_prev and m_curr > s_curr) else ""
        print(f"Date: {df.index[curr_pos].strftime('%Y-%m-%d')} | MACD: {m_curr:.3f} | Signal: {s_curr:.3f} | {cross}")

check_macd_crossover_debug("TORNTPHARM.NS")

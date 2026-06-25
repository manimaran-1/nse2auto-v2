import os
import pandas as pd
import indicators
import data_loader
import concurrent.futures
import logging
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_macd_crossover(symbol):
    try:
        # Fetch data for 1D timeframe - Using 6mo for indicator stability
        df = data_loader.fetch_data(symbol, period='6mo', interval='1d')
        if df.empty or len(df) < 50:
            return None
        
        macd_line, signal_line, _ = indicators.calculate_macd(df)
        
        # Check the last 30 trading days for a crossover
        # Bullish Crossover logic: MACD[i-1] <= Signal[i-1] AND MACD[i] > Signal[i]
        for i in range(1, 31):
            curr_pos = -i
            prev_pos = -i - 1
            
            # Boundary check
            if abs(prev_pos) > len(macd_line):
                break
                
            m_curr = macd_line.iloc[curr_pos]
            s_curr = signal_line.iloc[curr_pos]
            m_prev = macd_line.iloc[prev_pos]
            s_prev = signal_line.iloc[prev_pos]
            
            if m_prev <= s_prev and m_curr > s_curr:
                days_ago = i - 1
                return {
                    'Symbol': symbol,
                    'LTP': round(df['close'].iloc[-1], 2),
                    'MACD': round(m_curr, 3),
                    'Signal': round(s_curr, 3),
                    'Days Ago': days_ago,
                    'Crossover Date': df.index[curr_pos].strftime('%Y-%m-%d')
                }
        return None
    except Exception:
        return None

def main():
    logger.info("Fetching Nifty 500 symbols from NSE...")
    symbols = data_loader.get_nifty500_symbols()
    
    if not symbols:
        logger.error("Failed to retrieve Nifty 500 symbols.")
        return

    logger.info(f"Scanning {len(symbols)} symbols for MACD Bullish Crossover (1D)...")
    logger.info("Timeframe: 1D | Defining 'Recent' as within last 30 trading days.\n")
    
    # Check one symbol to get the latest date
    sample_df = data_loader.fetch_data(symbols[0], period='5d', interval='1d')
    if not sample_df.empty:
        latest_date = sample_df.index[-1].strftime('%d-%m-%Y')
        logger.info(f"Latest data in dataset: {latest_date}")
    
    matches = []
    # Use ThreadPoolExecutor for concurrent I/O (yfinance calls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_symbol = {executor.submit(check_macd_crossover, sym): sym for sym in symbols}
        
        total = len(symbols)
        completed = 0
        
        for future in concurrent.futures.as_completed(future_to_symbol):
            res = future.result()
            completed += 1
            if res:
                matches.append(res)
                logger.info(f"[{completed}/{total}] ✅ {res['Symbol']} - Crossover on {res['Crossover Date']}")
            elif completed % 50 == 0:
                logger.info(f"[{completed}/{total}] Scanning in progress...")

    print("\n" + "="*80)
    if matches:
        df_results = pd.DataFrame(matches).sort_values(by=['Days Ago', 'Symbol'])
        print("### NIFTY 500 MACD BULLISH CROSSOVER LIST (1D)")
        print(df_results.to_string(index=False))
        print("\n*Note: 'Days Ago' refers to the proximity of the crossover to the latest available data.*")
    else:
        print("No BULLISH MACD crossovers detected in the NIFTY 500 universe in the last 30 trading days.")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

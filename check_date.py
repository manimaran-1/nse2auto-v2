import indicators
import data_loader

symbol = "TORNTPHARM.NS"
df = data_loader.fetch_data(symbol, period='6mo', interval='1d')
if not df.empty:
    macd_line, signal_line, hist = indicators.calculate_macd(df)
    target_date = "2026-03-12"
    if target_date in df.index.strftime('%Y-%m-%d'):
        idx = df.index.strftime('%Y-%m-%d').tolist().index(target_date)
        m_curr = macd_line.iloc[idx]
        s_curr = signal_line.iloc[idx]
        m_prev = macd_line.iloc[idx-1]
        s_prev = signal_line.iloc[idx-1]
        print(f"Date: {target_date} | MACD: {m_curr:.3f} | Signal: {s_curr:.3f}")
        print(f"Prev Date: {df.index[idx-1].strftime('%Y-%m-%d')} | MACD: {m_prev:.3f} | Signal: {s_prev:.3f}")
        if m_prev <= s_prev and m_curr > s_curr:
             print("BULLISH CROSSOVER DETECTED!")
        else:
             print("NO BULLISH CROSSOVER.")
    else:
        print(f"Date {target_date} not found.")
else:
    print(f"Failed to fetch data for {symbol}")

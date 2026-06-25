import indicators
import data_loader

symbol = "TORNTPHARM.NS"
df = data_loader.fetch_data(symbol, period='6mo', interval='1d')
if not df.empty:
    macd_line, signal_line, hist = indicators.calculate_macd(df)
    print(f"\nLast 15 days for {symbol}:")
    for i in range(1, 16):
        idx = -i
        m = macd_line.iloc[idx]
        s = signal_line.iloc[idx]
        print(f"Date: {df.index[idx].strftime('%Y-%m-%d')} | MACD: {m:.3f} | Signal: {s:.3f} | Diff: {m-s:.3f}")
else:
    print(f"Failed to fetch data for {symbol}")

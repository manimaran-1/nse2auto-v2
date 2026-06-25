import pandas as pd
from datetime import datetime
from collections import Counter
import pytz

IST = pytz.timezone('Asia/Kolkata')

def format_volume(vol):
    """Formats large volumes into k/M suffixes for readability."""
    if vol >= 1_000_000:
        return f"{vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        return f"{vol/1_000:.0f}k"
    return str(int(vol))

def get_sentiment(avg_smi, avg_rsi):
    """Calculates an overall market sentiment based on averages."""
    if avg_smi > 60 and avg_rsi > 80:
        return "🔥 VERY BULLISH (Strongest trends and speed)"
    elif avg_smi > 40 or avg_rsi > 70:
        return "✅ BULLISH (Healthy upward movement)"
    return "⚖️ NEUTRAL (Gradual recovery or consolidation)"

def split_list_to_chunks(lines, limit):
    """
    Groups a list of lines into chunks each under the specified character limit.
    """
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_len = len(line) + 1 # +1 for newline
        if current_length + line_len > limit:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = line_len
        else:
            current_chunk.append(line)
            current_length += line_len
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def generate_report(df, universe, timeframe, limit=10):
    """
    NSE Market Analyst v2.9 - Technical Detail Refinement with Auto-Splitting.
    Returns: List of message strings formatted for Telegram.
    """
    if df.empty:
        return [(
            f"ℹ️ *NSE Market Scan Update*\n\n"
            f"📊 *Universe:* {universe}\n"
            f"⏰ *Timeframe:* {timeframe}\n"
            f"⚠️ No matches found.\n"
            f"📅 {datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')} IST"
        )]

    # 1. Deduplicate for Highlights
    unique_df = df.sort_values(by='Volume', ascending=False).drop_duplicates(subset='Stock Name').copy()
    total_found = len(df)
    now_ist = datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')
    
    # --- PROBABILITY RANKING — Refined V3 Enhanced 5-Factor Model ---
    top_trades_list = []
    top_classic_list = []
    if 'Day Open' in unique_df.columns:
        unique_df['Change_Pct'] = ((unique_df['LTP'] - unique_df['Day Open']) / unique_df['Day Open']) * 100

        # Ensure ATR exists, fallback to 2% of LTP if not found
        if 'ATR' not in unique_df.columns:
            unique_df['ATR'] = unique_df['LTP'] * 0.02
        else:
            unique_df['ATR'] = unique_df['ATR'].fillna(unique_df['LTP'] * 0.02)

        # 1. Dynamic Change (volatility-normalized, allowing negative score down to -15)
        atr_pct = ((unique_df['ATR'] / unique_df['Day Open']) * 100).clip(lower=0.5)
        change_norm = unique_df['Change_Pct'] / (atr_pct * 1.5)
        change_score = change_norm.clip(-0.5, 1.0) * 30

        # 2. SMI Zone (sweet spot 40-80, overbought decay above 80)
        import numpy as np
        smi_val = unique_df['SMI']
        smi_score = np.where(
            (smi_val >= 40) & (smi_val < 80), 
            20.0, 
            np.where(smi_val >= 80, 10.0, 0.0)
        )

        # 3. Normalized MACD (volatility-neutralized)
        macd_norm = unique_df['MACD'] / (unique_df['ATR'] * 3.0)
        macd_score = macd_norm.clip(0, 1.0) * 20

        # 4. RVOL (Floor penalty at -10, linear 1.0-1.5, uncapped bonus for extreme volume)
        rvol_val = unique_df['RVOL']
        rvol_score = np.where(
            rvol_val < 1.0,
            ((rvol_val - 1.0) * 10.0).clip(lower=-10.0),
            np.where(
                rvol_val < 1.5,
                ((rvol_val - 1.0) / 0.5) * 15.0,
                15.0 + (rvol_val - 1.5) * 2.0
            )
        )

        # 5. Sharpe-RS (Volatility-adjusted Relative Strength)
        vol_effective = unique_df['Volatility'].clip(lower=0.5)
        rs_score = (unique_df['Rel Strength'] / (vol_effective * 2.0)).clip(0, 1.0) * 15

        unique_df['Enhanced_Score'] = (
            change_score + smi_score + macd_score + rvol_score + rs_score
        ).fillna(0).clip(0, 100)

        unique_df['Classic_Score'] = (
            unique_df['Change_Pct'].clip(0, 5) / 5 * 40
            + unique_df['SMI'].clip(0, 100) / 100 * 30
            + unique_df['MACD'].clip(0, 5) / 5 * 30
        ).fillna(0).clip(0, 100)

        # 1. Top {limit} Enhanced V3 Trades
        top_ranked_enhanced = unique_df.nlargest(limit, 'Enhanced_Score')
        for _, row in top_ranked_enhanced.iterrows():
            diff = row['Enhanced_Score'] - row['Classic_Score']
            sign = "+" if diff >= 0 else ""
            cats_str = row.get('Category', '')
            cats_suffix = f" ({cats_str})" if cats_str else ""
            top_trades_list.append(
                f"• *{row['Stock Name']}*{cats_suffix} | Enhanced: *{row['Enhanced_Score']:.1f}* | Classic: {row['Classic_Score']:.1f} (Δ: {sign}{diff:.1f})"
            )

        # 2. Top {limit} Classic 3-Factor Trades
        top_ranked_classic = unique_df.nlargest(limit, 'Classic_Score')
        for _, row in top_ranked_classic.iterrows():
            cats_str = row.get('Category', '')
            cats_suffix = f" ({cats_str})" if cats_str else ""
            top_classic_list.append(
                f"• *{row['Stock Name']}*{cats_suffix} | Classic: *{row['Classic_Score']:.1f}* | Enhanced: {row['Enhanced_Score']:.1f}"
            )


    # --- MOMENTUM SIGNATURE (SQUEEZE BREAKOUTS) ---
    momentum_signature_list = []
    if 'is_momentum_signature' in unique_df.columns:
        sig_stocks = unique_df[unique_df['is_momentum_signature'] == True]
        for _, row in sig_stocks.iterrows():
            squeeze_icon = "🌀" if row.get('is_squeeze', False) else ""
            cats_str = row.get('Category', '')
            cats_suffix = f" ({cats_str})" if cats_str else ""
            momentum_signature_list.append(f"👉 🚀 *{row['Stock Name']}*{cats_suffix} {squeeze_icon}(RSI: {row['RSI']:.0f}, RS: {row.get('Rel Strength', 0):+.1f}, ADX: {row.get('ADX', 0)})")

    # --- TOP CATEGORY PICKING WITH INDICATORS ---
    def get_top_with_val(col, label_fn=lambda x: f"{x:.1f}", limit=3):
        top = unique_df.nlargest(limit, col)
        if top.empty: return ["-"]
        return [f"{r['Stock Name']} ({label_fn(r[col])})" for _, r in top.iterrows()]

    top_vol_list = get_top_with_val('Volume', format_volume)
    top_mom_list = get_top_with_val('Stoch RSI K', lambda x: f"RSI: {x:.0f}")
    top_trend_list = get_top_with_val('SMI', lambda x: f"SMI: {x:.1f}", limit=10)
    top_macd_list = get_top_with_val('MACD', lambda x: f"MACD: {x:.1f}")

    # --- SUPER SIGNAL DETECTION ---
    top_vol_names = unique_df.nlargest(3, 'Volume')['Stock Name'].tolist() if 'Volume' in unique_df.columns else []
    top_mom_names = unique_df.nlargest(3, 'Stoch RSI K')['Stock Name'].tolist() if 'Stoch RSI K' in unique_df.columns else []
    top_trend_names = unique_df.nlargest(3, 'SMI')['Stock Name'].tolist() if 'SMI' in unique_df.columns else []
    top_macd_names = unique_df.nlargest(3, 'MACD')['Stock Name'].tolist() if 'MACD' in unique_df.columns else []

    combined_leaders = top_vol_names + top_mom_names + top_trend_names + top_macd_names
    counts = Counter(combined_leaders)
    super_signals = []
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]
    for stock, count in sorted_counts:
        icon = "🔥" if count >= 3 else "⭐"
        if 'is_momentum_signature' in unique_df.columns:
            is_sig = unique_df[unique_df['Stock Name'] == stock]['is_momentum_signature'].any()
            if is_sig:
                icon = "🚀"
        super_signals.append(f"👉 {icon} *{stock}* (in {count} lists)")

    # --- INTRADAY PERFORMANCE ---
    intraday_winners = []
    if 'Change_Pct' in unique_df.columns:
        winners = unique_df[unique_df['Change_Pct'] > 0.3].nlargest(5, 'Change_Pct')
        for _, row in winners.iterrows():
            vwap_loc = f"V:{row['VWAP']:.0f}" if 'VWAP' in row else ""
            intraday_winners.append(f"👉 *{row['Stock Name']}* (+{row['Change_Pct']:.2f}% {vwap_loc})")

    # --- OTHER STATS ---
    top_cheap = unique_df.nsmallest(3, 'LTP')
    top_value = unique_df.nlargest(3, 'LTP')
    avg_rsi = df['Stoch RSI K'].mean() if 'Stoch RSI K' in df.columns else 0
    avg_smi = df['SMI'].mean() if 'SMI' in df.columns else 0
    sentiment = get_sentiment(avg_smi, avg_rsi)

    # Check if this universe should receive a detailed report
    is_detailed = any(keyword in universe for keyword in ["500", "Total Cash"])

    if not is_detailed:
        p_lines = [
            f"🚀 *NSE Scanner v2 Dual Method* | 📊 *{universe}*",
            f"----------------------------------------"
        ]
        if top_trades_list:
            p_lines.append(f"💎 *TOP {limit} HIGH-PROBABILITY TRADES*")
            p_lines.extend(top_trades_list)
            p_lines.append(f"----------------------------------------")
        
        if momentum_signature_list:
            p_lines.append(f"🚀 *MOMENTUM SIGNATURE (BREAKOUT)*")
            p_lines.extend(momentum_signature_list)
            
        return ["\n".join(p_lines)]

    # --- BUILD PART 1 LINES ---
    p1_lines = [
        f"🚀 *NSE Scanner v2 Dual Method* | 📊 *{universe}*",
        f"----------------------------------------"
    ]
    if top_trades_list:
        p1_lines.append(f"💎 *TOP {limit} HIGH-PROBABILITY TRADES*")
        p1_lines.extend(top_trades_list)
        p1_lines.append(f"----------------------------------------")

    if momentum_signature_list:
        p1_lines.append(f"🚀 *MOMENTUM SIGNATURE (BREAKOUT)*")
        p1_lines.extend(momentum_signature_list) 
        p1_lines.append(f"----------------------------------------")

    p1_lines.extend([
        f"🏁 *SENTIMENT:* _{sentiment}_",
        f"💡 _(Based on Group Avg SMI & Stoch RSI K)_",
        f"----------------------------------------",
        f"✅ *Signals:* {total_found} | *TF:* {timeframe} | _{now_ist}_"
    ])

    # Trigger splitting for Part 1 (Limit: 900 characters for caption safety)
    part1_chunks = split_list_to_chunks(p1_lines, 900)

    # --- BUILD PART 2 LINES ---
    p2_lines = []
    if top_classic_list:
        p2_lines.append(f"🏆 *TOP {limit} CLASSIC 3-FACTOR TRADES*")
        p2_lines.extend(top_classic_list)
        p2_lines.append(f"----------------------------------------")
    
    p2_lines.append(f"🏅 *MULTI-CATEGORY LEADERS*")
    if super_signals:
        p2_lines.extend(super_signals)
    else:
        p2_lines.append("👉 _None found in multiple lists_")
    
    p2_lines.extend([
        f"",
        f"🏆 *INTRADAY WINNERS* (+% from 9:15)",
        f"_Strong session trend stocks_"
    ])
    if intraday_winners:
        p2_lines.extend(intraday_winners)
    else:
        p2_lines.append("👉 _No significant session gainers_")

    p2_lines.extend([
        f"----------------------------------------",
        f"📈 *TOP 10 SMI (Trend Strength):*",
        f"{', '.join(top_trend_list)}",
        f"",
        f"💎 *Top Vol:* {', '.join(top_vol_list)}",
        f"",
        f"⚡ *Top RSI:* {', '.join(top_mom_list)}",
        f"",
        f"🔥 *Top MACD:* {', '.join(top_macd_list)}",
        f"----------------------------------------",
        f"💰 *LOW:* {', '.join(top_cheap['Stock Name'].tolist())}",
        f"💰 *HIGH:* {', '.join(top_value['Stock Name'].tolist())}"
    ])

    # Trigger splitting for Part 2 (Limit: 4000 characters for message)
    part2_chunks = split_list_to_chunks(p2_lines, 4000)

    # Combine everything
    return part1_chunks + part2_chunks

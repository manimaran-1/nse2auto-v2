import streamlit as st
import pandas as pd
import scanner
import data_loader
import config
import reporter
import pytz
import os
import requests
import io
import logging
from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------------------
# PAGE CONFIG — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NSE Stock Scanner 2.0",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# THEME DEFINITIONS
# Each theme is a complete palette: bg, fg, sidebar_bg, accent, card_bg,
# input_bg, border_color, muted.
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    "🌌 Dark Blue": {
        "bg":           "linear-gradient(135deg,#080c14 0%,#0f172a 100%)",
        "bg_solid":     "#080c14",
        "fg":           "#f1f5f9",
        "sidebar_bg":   "#0f172a",
        "accent":       "#00d4ff",
        "card_bg":      "rgba(255,255,255,0.04)",
        "input_bg":     "#0f172a",
        "border":       "rgba(255,255,255,0.10)",
        "muted":        "#94a3b8",
    },
    "☀️ Light Mode": {
        "bg":           "#f8fafc",
        "bg_solid":     "#f8fafc",
        "fg":           "#0f172a",
        "sidebar_bg":   "#f1f5f9",
        "accent":       "#2563eb",
        "card_bg":      "#ffffff",
        "input_bg":     "#ffffff",
        "border":       "rgba(0,0,0,0.12)",
        "muted":        "#64748b",
    },
    "🌑 Midnight Black": {
        "bg":           "#050505",
        "bg_solid":     "#050505",
        "fg":           "#f0f0f0",
        "sidebar_bg":   "#0d0d0d",
        "accent":       "#a855f7",
        "card_bg":      "rgba(255,255,255,0.05)",
        "input_bg":     "#111111",
        "border":       "rgba(255,255,255,0.08)",
        "muted":        "#888888",
    },
    "🌿 Emerald Green": {
        "bg":           "linear-gradient(135deg,#064e3b 0%,#022c22 100%)",
        "bg_solid":     "#033526",
        "fg":           "#ecfdf5",
        "sidebar_bg":   "#064e3b",
        "accent":       "#10b981",
        "card_bg":      "rgba(255,255,255,0.06)",
        "input_bg":     "#043d2c",
        "border":       "rgba(255,255,255,0.12)",
        "muted":        "#6ee7b7",
    },
    "🔥 Warm Amber": {
        "bg":           "linear-gradient(135deg,#451a03 0%,#1c1917 100%)",
        "bg_solid":     "#2c1202",
        "fg":           "#fffbeb",
        "sidebar_bg":   "#292524",
        "accent":       "#f59e0b",
        "card_bg":      "rgba(255,255,255,0.05)",
        "input_bg":     "#1c1309",
        "border":       "rgba(255,255,255,0.10)",
        "muted":        "#fcd34d",
    },
}

THEME_NAMES = list(THEMES.keys())


def apply_theme(t: dict[str, str]) -> None:
    """
    Inject a comprehensive CSS variable block that covers every Streamlit
    surface: main area, sidebar (all children), inputs, dropdowns, tabs,
    DataFrames, expanders, metrics, buttons, banners.
    """
    st.markdown(
        f"""
        <style>
        /* ── Google Font ──────────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap');

        /* ── CSS Variables ────────────────────────────────────────────── */
        :root {{
            --fg:         {t['fg']};
            --bg-solid:   {t['bg_solid']};
            --sidebar-bg: {t['sidebar_bg']};
            --accent:     {t['accent']};
            --card-bg:    {t['card_bg']};
            --input-bg:   {t['input_bg']};
            --border:     {t['border']};
            --muted:      {t['muted']};
            --font:       'Outfit', sans-serif;
        }}

        /* ── Global App Surface ───────────────────────────────────────── */
        html, body, .stApp {{
            font-family: var(--font) !important;
            background: {t['bg']} !important;
            color: var(--fg) !important;
        }}

        /* ── Set Text Color ───────────────────────────────────────────── */
        p, span, div, h1, h2, h3, h4, h5, h6,
        li, td, th, label, small, strong, em,
        .stMarkdown, .stText, .element-container {{
            color: var(--fg) !important;
        }}

        /* ── Set Text Font ────────────────────────────────────────────── */
        /* Generic 'div' and 'span' are excluded to prevent overriding Streamlit icon fonts */
        html, body, .stApp,
        p, h1, h2, h3, h4, h5, h6,
        li, td, th, label, small, strong, em,
        .stMarkdown, .stText {{
            font-family: var(--font) !important;
        }}

        /* ── Sidebar — full surface ───────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: var(--sidebar-bg) !important;
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
        [data-testid="stSidebar"] [data-testid="stHeading"] {{
            color: var(--fg) !important;
            font-family: var(--font) !important;
        }}

        /* ── Sidebar — section headers / subheaders ───────────────────── */
        [data-testid="stSidebar"] .stSubheader,
        [data-testid="stSidebar"] [data-testid="stHeading"] p {{
            color: var(--accent) !important;
        }}

        /* ── Selectbox & Multiselect ──────────────────────────────────── */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] svg {{
            background-color: var(--input-bg) !important;
            color: var(--fg) !important;
            border-color: var(--border) !important;
        }}
        /* Dropdown popup list */
        div[data-baseweb="popover"],
        ul[data-baseweb="menu"],
        ul[data-baseweb="menu"] li,
        [data-baseweb="menu-item"],
        [data-baseweb="option"] {{
            background-color: var(--bg-solid) !important;
            color: var(--fg) !important;
        }}
        /* Apply font to text items inside dropdowns, but NOT globally to all descendents to keep icons safe */
        div[data-baseweb="popover"] [data-baseweb="menu-item"],
        div[data-baseweb="popover"] li,
        [data-baseweb="option"] {{
            font-family: var(--font) !important;
        }}
        [data-baseweb="option"]:hover,
        [data-baseweb="menu-item"]:hover {{
            background-color: var(--accent) !important;
            color: #fff !important;
        }}

        /* ── Text Inputs & Textareas ──────────────────────────────────── */
        input[type="text"], input[type="password"], input[type="number"],
        textarea {{
            background-color: var(--input-bg) !important;
            color: var(--fg) !important;
            border: 1px solid var(--border) !important;
            font-family: var(--font) !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: var(--muted) !important;
        }}

        /* ── Checkbox & Radio ─────────────────────────────────────────── */
        [data-testid="stCheckbox"] span,
        [data-testid="stRadio"] span {{
            color: var(--fg) !important;
        }}

        /* ── Buttons ──────────────────────────────────────────────────── */
        .stButton > button {{
            background-color: var(--accent) !important;
            color: #ffffff !important;
            border: none !important;
            font-family: var(--font) !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            transition: opacity 0.2s;
        }}
        .stButton > button:hover {{
            opacity: 0.88;
        }}

        /* ── Download Button ──────────────────────────────────────────── */
        .stDownloadButton > button {{
            background-color: var(--card-bg) !important;
            color: var(--fg) !important;
            border: 1px solid var(--border) !important;
            font-family: var(--font) !important;
            border-radius: 8px !important;
        }}

        /* ── Tabs ─────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: var(--card-bg) !important;
            border-radius: 10px 10px 0 0 !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: transparent !important;
            color: var(--muted) !important;
            font-family: var(--font) !important;
            font-weight: 500 !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: var(--accent) !important;
            border-bottom: 2px solid var(--accent) !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            background-color: var(--card-bg) !important;
        }}

        /* ── Expanders ────────────────────────────────────────────────── */
        .streamlit-expanderHeader,
        [data-testid="stExpander"] summary {{
            background-color: var(--card-bg) !important;
            color: var(--fg) !important;
            font-family: var(--font) !important;
        }}
        [data-testid="stExpanderToggleIcon"] {{
            background-color: transparent !important;
            color: var(--fg) !important;
        }}
        [data-testid="stExpander"] {{
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        [data-testid="stExpander"] > div {{
            background-color: var(--card-bg) !important;
        }}

        /* ── DataFrames / Tables ──────────────────────────────────────── */
        .stDataFrame {{
            background-color: var(--card-bg) !important;
        }}
        .stDataFrame th, .stDataFrame td,
        [data-testid="stDataFrame"] th,
        [data-testid="stDataFrame"] td {{
            color: var(--fg) !important;
            background-color: var(--card-bg) !important;
            font-family: var(--font) !important;
        }}
        /* DataFrame header row */
        [data-testid="stDataFrame"] th {{
            background-color: var(--input-bg) !important;
            color: var(--accent) !important;
            font-weight: 600 !important;
        }}

        /* ── Metrics ──────────────────────────────────────────────────── */
        [data-testid="stMetric"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {{
            color: var(--fg) !important;
            font-family: var(--font) !important;
        }}
        .metric-card {{
            background: var(--card-bg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px;
            padding: 16px;
            color: var(--fg) !important;
        }}

        /* ── Info / Success / Warning / Error banners ─────────────────── */
        [data-testid="stAlert"] {{
            background-color: var(--card-bg) !important;
            border: 1px solid var(--border) !important;
            color: var(--fg) !important;
        }}
        [data-testid="stAlert"] * {{
            color: var(--fg) !important;
        }}

        /* ── Progress Bar ─────────────────────────────────────────────── */
        [data-testid="stProgress"] > div > div {{
            background-color: var(--accent) !important;
        }}

        /* ── Spinner ──────────────────────────────────────────────────── */
        [data-testid="stSpinner"] * {{
            color: var(--fg) !important;
        }}

        /* ── Markdown horizontal rule ─────────────────────────────────── */
        hr {{
            border-color: var(--border) !important;
        }}

        /* ── Streamlit Header / Top Bar (Hides the white space at the top) ── */
        header, [data-testid="stHeader"] {{
            display: none !important;
        }}
        .block-container {{
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }}

        /* ── Protect Streamlit Icon Fonts ─────────────────────────────── */
        .material-icons,
        .material-symbols-outlined,
        [data-testid="stIcon"],
        [data-testid="stExpanderToggleIcon"] svg,
        [data-testid="stSidebar"] [data-testid="stIcon"],
        div[data-baseweb="popover"] svg,
        div[data-baseweb="popover"] span:empty,
        div[data-baseweb="popover"] [class*="icon"],
        div[data-baseweb="popover"] [class*="Icon"] {{
            font-family: "Material Icons", "Material Symbols Outlined", sans-serif !important;
        }}

        /* ── Hide Streamlit branding ──────────────────────────────────── */
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        .stDeployButton {{ display: none !important; }}

        /* ── Scrollbar ────────────────────────────────────────────────── */
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-solid); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# THEME SELECTION — sidebar widget
# ---------------------------------------------------------------------------
if "theme_choice" not in st.session_state or st.session_state.theme_choice not in THEME_NAMES:
    st.session_state.theme_choice = THEME_NAMES[0]

theme_choice = st.sidebar.selectbox(
    "🎨 App Theme",
    THEME_NAMES,
    index=THEME_NAMES.index(st.session_state.theme_choice),
    key="theme_select",
)
st.session_state.theme_choice = theme_choice

# Apply the selected theme immediately
apply_theme(THEMES[theme_choice])

# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "scan_metadata" not in st.session_state:
    st.session_state.scan_metadata = {
        "universe": "", "timeframe": "", "data_source": "", "live_universe": False,
        "enable_inst_filters": True, "min_turnover_crores": 10.0, "min_age_days": 180, "regime_filter": "None",
        "max_workers": 12
    }
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

# ---------------------------------------------------------------------------
# SECURE CREDENTIALS — gracefully degrade when secrets.toml absent
# ---------------------------------------------------------------------------
try:
    _secrets = st.secrets
    BOT_TOKEN = _secrets.get("TELEGRAM_BOT_TOKEN", None) or config.TELEGRAM_BOT_TOKEN
    CHAT_ID   = _secrets.get("TELEGRAM_CHAT_ID",   None) or config.TELEGRAM_CHAT_ID
    SEND_CSV  = _secrets.get("SEND_CSV", None)
    if SEND_CSV is None:
        SEND_CSV = config.SEND_CSV
    else:
        SEND_CSV = str(SEND_CSV).lower() == "true"
    _APP_PASSWORD = _secrets.get("password", None)
except Exception:
    BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
    CHAT_ID   = config.TELEGRAM_CHAT_ID
    SEND_CSV  = config.SEND_CSV
    _APP_PASSWORD = None

# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------
def check_password() -> bool:
    if not _APP_PASSWORD:
        return True  # No password configured → open access
    if st.session_state.password_correct:
        return True
    st.markdown("<h2 style='text-align:center;'>🔐 Secure Access Required</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            entered = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if entered == str(_APP_PASSWORD):
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
    return False

if not check_password():
    st.stop()

# ---------------------------------------------------------------------------
# SIDEBAR — rest of controls
# ---------------------------------------------------------------------------
with st.sidebar.expander("📈 Market Status", expanded=False):
    now_ist = data_loader.get_now_ist()
    current_time_ist = now_ist.strftime("%I:%M %p")
    current_day = now_ist.strftime("%A")
    if data_loader.is_market_open():
        st.success(f"🟢 NSE: Open\n\n({current_day}, {current_time_ist} IST)")
    else:
        st.warning(f"🔴 NSE: Closed\n\n({current_day}, {current_time_ist} IST)")

st.sidebar.header("Scan Setup")
indices_dict = data_loader.get_all_indices_dict()
universe_options = list(indices_dict.keys()) + ["Custom List"]
default_idx = (
    universe_options.index("Total Cash Segment (~2000+)")
    if "Total Cash Segment (~2000+)" in universe_options
    else 0
)
selected_universe = st.sidebar.selectbox("Market Universe", universe_options, index=default_idx)

live_universe = st.sidebar.checkbox(
    "📡 Live Universe Fetch",
    value=False,
    help="OFF = fast local CSV cache. ON = downloads fresh lists from NSE archives.",
)

timeframe_options = ["1d", "1wk", "1mo", "1m", "5m", "15m", "1h"]
selected_timeframe = st.sidebar.selectbox("Timeframe (Interval)", timeframe_options, index=timeframe_options.index("1h"))

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Data Source")
data_source_options = ["yflib", "yfapi"]
selected_data_source = st.sidebar.selectbox("Data Fetch Method", data_source_options, index=1)
max_workers = st.sidebar.slider(
    "Concurrency (Workers)",
    min_value=1,
    max_value=24,
    value=config.MAX_WORKERS,
    help="Number of concurrent download threads for fetching stock data."
)

st.sidebar.markdown("---")
with st.sidebar.expander("🏛️ Institutional Filters", expanded=True):
    enable_inst_filters = st.checkbox("Enable Liquidity & Age Funnel", value=True, help="Filters out thinly traded assets and new listings")
    min_turnover_crores = st.number_input("Min Daily Turnover (₹ Crores)", min_value=0.1, max_value=1000.0, value=10.0, step=1.0, help="Average daily Rupee turnover over the last 20 trading days.")
    min_age_days = st.number_input("Min Listing Age (Days)", min_value=30, max_value=3650, value=180, step=30, help="Minimum age since listing.")
    regime_filter = st.selectbox("Trend Regime Filter", ["None", "Price > EMA 50", "Price > EMA 200"], index=0, help="Filter out stocks below their long-term trendline.")

# Reset results when any scan parameter changes
_meta = st.session_state.scan_metadata
if (
    selected_universe  != _meta["universe"]
    or selected_timeframe  != _meta["timeframe"]
    or selected_data_source != _meta["data_source"]
    or live_universe       != _meta["live_universe"]
    or enable_inst_filters != _meta.get("enable_inst_filters", True)
    or min_turnover_crores != _meta.get("min_turnover_crores", 10.0)
    or min_age_days        != _meta.get("min_age_days", 180)
    or regime_filter       != _meta.get("regime_filter", "None")
    or max_workers         != _meta.get("max_workers", 12)
):
    st.session_state.results_df = None
    st.session_state.scan_metadata = {
        "universe": selected_universe,
        "timeframe": selected_timeframe,
        "data_source": selected_data_source,
        "live_universe": live_universe,
        "enable_inst_filters": enable_inst_filters,
        "min_turnover_crores": min_turnover_crores,
        "min_age_days": min_age_days,
        "regime_filter": regime_filter,
        "max_workers": max_workers,
    }

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Cache Control"):
    if st.button("🗑️ Clear OHLCV Cache"):
        count = data_loader.clear_ohlcv_cache()
        st.success(f"Cleared {count} cached files")

# ---------------------------------------------------------------------------
# SYMBOL LOADING
# ---------------------------------------------------------------------------
symbols: list[str] = []
if selected_universe == "Custom List":
    custom_input = st.sidebar.text_area("Symbols (comma separated)", "RELIANCE, TCS")
    if custom_input:
        symbols = [s.strip() for s in custom_input.split(",")]
        try:
            df_custom = pd.DataFrame({
                "Symbol": [s.replace("NSE:", "").replace("-EQ", "") for s in symbols]
            })
            df_custom.to_csv(
                os.path.join(data_loader.PERMANENT_DIR, "custom_list.csv"), index=False
            )
        except Exception:
            pass
else:
    with st.spinner(f"Loading {selected_universe} constituents..."):
        internal_universe = indices_dict.get(selected_universe, selected_universe)
        symbols = data_loader.get_index_constituents(internal_universe, live_fetch=live_universe)
        if not symbols:
            st.warning("Could not load constituents; using Nifty 50 fallback.")
            symbols = data_loader.get_nifty50_symbols(live_fetch=live_universe)

# ---------------------------------------------------------------------------
# MAIN HEADER
# ---------------------------------------------------------------------------
st.title("NSE Stock Scanner 📈 v2.0")
st.markdown(
    "Automated Technical Analysis Scanner (EMA · Stoch RSI · SMI · MACD) "
    "with dual-model probability scoring"
)

st.info(
    f"**Scanning**: {selected_universe} | **Symbols**: {len(symbols)} | "
    f"**Interval**: {selected_timeframe} | **Data Source**: {selected_data_source} | "
    f"**Live Universe**: {live_universe}"
)

# ---------------------------------------------------------------------------
# TELEGRAM HELPER
# ---------------------------------------------------------------------------
def send_to_telegram(df: pd.DataFrame, universe: str, timeframe: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        st.error(
            "🚨 Telegram Bot Token or Chat ID not configured. "
            "Set them in `.env` or environment variables."
        )
        return False

    report_parts = reporter.generate_report(df, universe, timeframe, limit=20)
    if not report_parts:
        return False

    msg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        if SEND_CSV:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)

            doc_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            files = {"document": ("nse2_scan_results.csv", csv_buffer.getvalue())}
            data  = {"chat_id": CHAT_ID, "caption": report_parts[0], "parse_mode": "Markdown"}

            resp = requests.post(doc_url, files=files, data=data, timeout=20)
            if resp.status_code != 200:
                st.error(f"Telegram Error (Doc): {resp.text}")
                return False
        else:
            resp = requests.post(msg_url, json={"chat_id": CHAT_ID, "text": report_parts[0], "parse_mode": "Markdown"}, timeout=15)
            if resp.status_code != 200:
                st.error(f"Telegram Error: {resp.text}")
                return False

        for part in report_parts[1:]:
            requests.post(msg_url, json={"chat_id": CHAT_ID, "text": part, "parse_mode": "Markdown"}, timeout=15)
        return True
    except Exception as e:
        st.error(f"Failed to send to Telegram: {e}")
    return False


# ---------------------------------------------------------------------------
# SCORE CALCULATION HELPERS
# ---------------------------------------------------------------------------
def _compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Classic 3-Factor and Refined V3 Enhanced 5-Factor scores.
    Returns the modified DataFrame.
    """
    df = df.copy()

    if df.empty:
        df["Classic_Score"]  = 0.0
        df["Enhanced_Score"] = 0.0
        return df

    if "Day Open" not in df.columns:
        df["Classic_Score"]  = 0.0
        df["Enhanced_Score"] = 0.0
        return df

    df["Change_Pct"] = ((df["LTP"] - df["Day Open"]) / df["Day Open"]) * 100

    # Ensure ATR exists, fallback to 2% of LTP if not found
    if "ATR" not in df.columns:
        df["ATR"] = df["LTP"] * 0.02
    else:
        df["ATR"] = df["ATR"].fillna(df["LTP"] * 0.02)

    # — Classic 3-Factor —
    df["Classic_Score"] = (
        df["Change_Pct"].clip(0, 5) / 5 * 40
        + df["SMI"].clip(0, 100) / 100 * 30
        + df["MACD"].clip(0, 5) / 5 * 30
    ).fillna(0).clip(0, 100)

    # — Refined V3 Enhanced 5-Factor —
    # 1. Dynamic Change (volatility-normalized, allowing negative score down to -15)
    atr_pct = ((df["ATR"] / df["Day Open"]) * 100).clip(lower=0.5)
    change_norm = df["Change_Pct"] / (atr_pct * 1.5)
    change_5f = change_norm.clip(-0.5, 1.0) * 30

    # 2. SMI Zone (Trend buying sweet spot 40-80, overbought decay above 80)
    import numpy as np
    smi_val = df["SMI"]
    smi_5f = np.where(
        (smi_val >= 40) & (smi_val < 80), 
        20.0, 
        np.where(smi_val >= 80, 10.0, 0.0)
    )

    # 3. Normalized MACD (Price-scale independent, volatility-neutralized)
    macd_norm = df["MACD"] / (df["ATR"] * 3.0)
    macd_5f = macd_norm.clip(0, 1.0) * 20

    # 4. RVOL (Floor penalty at -10, linear 1.0-1.5, uncapped bonus for extreme volume)
    rvol_val = df["RVOL"]
    rvol_5f = np.where(
        rvol_val < 1.0,
        ((rvol_val - 1.0) * 10.0).clip(lower=-10.0),
        np.where(
            rvol_val < 1.5,
            ((rvol_val - 1.0) / 0.5) * 15.0,
            15.0 + (rvol_val - 1.5) * 2.0
        )
    )

    # 5. Sharpe-RS (Volatility-adjusted Relative Strength)
    vol_effective = df["Volatility"].clip(lower=0.5)
    rs_5f = (df["Rel Strength"] / (vol_effective * 2.0)).clip(0, 1.0) * 15

    # Combined score, clipped to standard [0, 100] range
    df["Enhanced_Score"] = (
        change_5f + smi_5f + macd_5f + rvol_5f + rs_5f
    ).fillna(0).clip(0, 100)

    return df


# ---------------------------------------------------------------------------
# SCAN EXECUTION
# ---------------------------------------------------------------------------
if st.button("🚀 Start Market Scan", width="stretch"):
    if not symbols:
        st.error("No valid symbols found.")
    else:
        ds_map = {"yflib": "yfinance", "yfapi": "yahoo"}
        data_loader.set_data_source(ds_map.get(selected_data_source, "yahoo"))

        progress_bar = st.progress(0, text="Initialising scan...")

        def _update_progress(completed: int, total: int) -> None:
            pct = min(completed / total, 1.0)
            progress_bar.progress(pct, text=f"Scanning {completed}/{total} stocks…")

        with st.spinner(f"Scanning {len(symbols)} stocks… please wait."):
            results_df = scanner.scan_market(
                symbols, 
                interval=selected_timeframe, 
                progress_callback=_update_progress,
                enable_inst_filters=enable_inst_filters,
                min_turnover_crores=min_turnover_crores,
                min_age_days=min_age_days,
                regime_filter=regime_filter,
                max_workers=max_workers
            )
            progress_bar.empty()

            if not results_df.empty:
                st.session_state.results_df = results_df.sort_values(
                    by="Signal Time", ascending=False
                )
            else:
                st.session_state.results_df = "EMPTY"

# ---------------------------------------------------------------------------
# PERSISTENT RESULTS DISPLAY
# ---------------------------------------------------------------------------
if st.session_state.results_df is not None:
    if isinstance(st.session_state.results_df, str):
        st.warning("No matches found for the selected criteria.")
    else:
        results_df = st.session_state.results_df.copy()

        # De-duplicate (highest volume per stock) and compute scores
        unique_df = (
            results_df.sort_values(by="Volume", ascending=False)
            .drop_duplicates(subset="Stock Name")
            .copy()
        )
        unique_df = _compute_scores(unique_df)

        # ── Derived sub-tables (Un-sliced, full sorted lists) ─────────
        top_classic_df_all = unique_df.sort_values(by="Classic_Score", ascending=False)[
            ["Stock Name", "Category", "Classic_Score", "LTP", "Change_Pct", "SMI", "MACD"]
        ]

        enhanced_cols = ["Stock Name", "Category", "Enhanced_Score", "LTP", "Change_Pct",
                         "SMI", "MACD", "RVOL", "Rel Strength"]
        for extra in ("Volatility", "Vol-Adjusted RS"):
            if extra in unique_df.columns:
                enhanced_cols.append(extra)
        top_enhanced_df_all = unique_df.sort_values(by="Enhanced_Score", ascending=False)[enhanced_cols]

        mom_sig_df_all = (
            unique_df[unique_df["is_momentum_signature"] == True]
            .sort_values(by="Rel Strength", ascending=False)[
                ["Stock Name", "LTP", "RSI", "Rel Strength", "ADX", "is_squeeze"]
            ]
        )

        # Helper function for Super Signals
        def _top_names(col: str, n: int) -> list[str]:
            return unique_df.nlargest(n, col)["Stock Name"].tolist() if col in unique_df.columns else []

        top_vol_df_all  = unique_df.sort_values(by="Volume", ascending=False)[["Stock Name", "Volume", "LTP"]]
        top_rsi_df_all  = unique_df.sort_values(by="Stoch RSI K", ascending=False)[["Stock Name", "Stoch RSI K", "LTP"]]
        top_smi_df_all  = unique_df.sort_values(by="SMI", ascending=False)[["Stock Name", "SMI", "LTP"]]
        top_macd_df_all = unique_df.sort_values(by="MACD", ascending=False)[["Stock Name", "MACD", "LTP"]]

        winners_df_all = pd.DataFrame()
        if "Change_Pct" in unique_df.columns:
            winners_df_all = unique_df[unique_df["Change_Pct"] > 0.3].sort_values(
                by="Change_Pct", ascending=False
            )[["Stock Name", "Change_Pct", "LTP", "VWAP"]]

        # ── TABS ──────────────────────────────────────────────────────
        tab_sig, tab_prob, tab_mom, tab_leaders, tab_winners = st.tabs([
            "🔍 Technical Signals",
            "💎 Top Probability Comparison",
            "🚀 Momentum Signatures",
            "🏆 Category Leaders & Super Signals",
            "🎖️ Intraday Winners",
        ])

        # ── Tab 1: Technical Signals ─────────────────────────────────
        with tab_sig:
            st.markdown(f"### 🔍 All Scanned Signals ({len(results_df)} total)")
            PAGE_SIZE = 100
            if len(results_df) > PAGE_SIZE:
                total_pages = (len(results_df) + PAGE_SIZE - 1) // PAGE_SIZE
                col_pg1, col_pg2 = st.columns([1, 2])
                with col_pg1:
                    page_num = st.number_input(
                        "Page", min_value=1, max_value=total_pages, value=1, step=1, key="main_page_num"
                    )
                with col_pg2:
                    pg_start = (page_num - 1) * PAGE_SIZE
                    pg_end   = min(pg_start + PAGE_SIZE, len(results_df))
                    st.markdown(
                        f"<div style='padding-top:32px;color:var(--muted);'>"
                        f"Rows {pg_start+1}–{pg_end} of {len(results_df)}</div>",
                        unsafe_allow_html=True,
                    )
                show_df = results_df.iloc[pg_start:pg_end]
            else:
                show_df = results_df

            st.dataframe(
                show_df,
                column_config={
                    "Stock Name":  "Symbol",
                    "LTP":         st.column_config.NumberColumn("LTP",    format="₹ %.2f"),
                    "Signal Time": "Time (IST)",
                    "Volume":      st.column_config.NumberColumn("Volume", format="%d"),
                    "RVOL":        st.column_config.NumberColumn("RVOL",   format="%.2fx"),
                    **{
                        f"EMA{l}": st.column_config.NumberColumn(f"EMA {l}", format="%.2f")
                        for l in config.STRATEGY_CONFIG["EMA"]
                    },
                },
                hide_index=True,
                width="stretch",
            )

        # ── Tab 2: Side-by-Side Probability Comparison ───────────────
        with tab_prob:
            st.markdown("### 💎 Trade Probability Model Comparison")
            st.markdown(
                "*Standard 3-Factor (absolute change) vs Enhanced 5-Factor "
                "(benchmark-relative + volume-confirmed + volatility-adjusted).*"
            )

            # Full comparison table
            col_all_title, col_all_opt = st.columns([3, 1])
            with col_all_opt:
                limit_all = st.number_input(
                    "Rows to show", min_value=1, max_value=200, value=20, key="limit_tab2_all"
                )
            with col_all_title:
                st.subheader(f"📊 Top {limit_all} Scoring Stocks (Full Universe)")

            compare_all_df = unique_df.copy()
            compare_all_df["Score Difference"] = (
                compare_all_df["Enhanced_Score"] - compare_all_df["Classic_Score"]
            )
            show_cols = [
                "Stock Name", "Category", "Classic_Score", "Enhanced_Score", "Score Difference",
                "LTP", "Change_Pct", "SMI", "MACD", "RVOL", "Rel Strength",
            ]
            for extra in ("Volatility", "Vol-Adjusted RS"):
                if extra in compare_all_df.columns:
                    show_cols.append(extra)
            compare_all_df = compare_all_df[show_cols].sort_values(
                by="Enhanced_Score", ascending=False
            ).head(limit_all)
            st.dataframe(
                compare_all_df,
                column_config={
                    "Stock Name":      "Symbol",
                    "Classic_Score":   st.column_config.NumberColumn("Classic Score",  format="%.1f / 100"),
                    "Enhanced_Score":  st.column_config.NumberColumn("Enhanced Score", format="%.1f / 100"),
                    "Score Difference": st.column_config.NumberColumn("Δ (Enhanced − Classic)", format="%+.1f"),
                    "LTP":             st.column_config.NumberColumn("LTP",      format="₹ %.2f"),
                    "Change_Pct":      st.column_config.NumberColumn("Session %", format="%.2f%%"),
                    "SMI":             st.column_config.NumberColumn("SMI",      format="%.1f"),
                    "MACD":            st.column_config.NumberColumn("MACD",     format="%.2f"),
                    "RVOL":            st.column_config.NumberColumn("RVOL",     format="%.2fx"),
                    "Rel Strength":    st.column_config.NumberColumn("RS vs Nifty",   format="%.2f%%"),
                    "Volatility":      st.column_config.NumberColumn("Daily Vol",      format="%.2f%%"),
                    "Vol-Adjusted RS": st.column_config.NumberColumn("Vol-Adj RS",     format="%.2f"),
                },
                hide_index=True,
                width="stretch",
            )

            st.markdown("---")
            col_lead_title, col_lead_opt = st.columns([3, 1])
            with col_lead_opt:
                limit_leaders = st.number_input(
                    "Rows to show", min_value=1, max_value=100, value=20, key="limit_tab2_leaders"
                )
            with col_lead_title:
                st.subheader(f"🏆 Top {limit_leaders} Leaders — Side-by-Side")
            col_c, col_e = st.columns(2)

            with col_c:
                st.subheader("🏆 Standard 3-Factor (Classic)")
                if not top_classic_df_all.empty:
                    st.dataframe(
                        top_classic_df_all.head(limit_leaders),
                        column_config={
                            "Stock Name":  "Symbol",
                            "Classic_Score": st.column_config.NumberColumn("Score", format="%.1f / 100"),
                            "LTP":         st.column_config.NumberColumn("LTP",   format="₹ %.2f"),
                            "Change_Pct":  st.column_config.NumberColumn("Session %", format="%.2f%%"),
                            "SMI":         st.column_config.NumberColumn("SMI",   format="%.1f"),
                            "MACD":        st.column_config.NumberColumn("MACD",  format="%.2f"),
                        },
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info("No score data available yet.")

            with col_e:
                st.subheader("🚀 Enhanced 5-Factor (Improvised)")
                if not top_enhanced_df_all.empty:
                    st.dataframe(
                        top_enhanced_df_all.head(limit_leaders),
                        column_config={
                            "Stock Name":    "Symbol",
                            "Enhanced_Score": st.column_config.NumberColumn("Score", format="%.1f / 100"),
                            "LTP":           st.column_config.NumberColumn("LTP",   format="₹ %.2f"),
                            "Change_Pct":    st.column_config.NumberColumn("Session %", format="%.2f%%"),
                            "SMI":           st.column_config.NumberColumn("SMI",   format="%.1f"),
                            "MACD":          st.column_config.NumberColumn("MACD",  format="%.2f"),
                            "RVOL":          st.column_config.NumberColumn("RVOL",  format="%.2fx"),
                            "Rel Strength":  st.column_config.NumberColumn("RS vs Nifty", format="%.2f%%"),
                            "Volatility":    st.column_config.NumberColumn("Daily Vol",   format="%.2f%%"),
                            "Vol-Adjusted RS": st.column_config.NumberColumn("Vol-Adj RS", format="%.2f"),
                        },
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info("No score data available yet.")

        # ── Tab 3: Momentum Signatures ───────────────────────────────
        with tab_mom:
            st.markdown("### 🚀 Momentum Signatures (Squeeze Breakouts)")
            st.markdown(
                "*Launchpad squeezes that triggered breakouts: strict EMA alignment, "
                "RSI > 60, MACD hist > 0, BBW ≤ 0.05, and volume > 2× average.*"
            )
            col_mom_title, col_mom_opt = st.columns([3, 1])
            with col_mom_opt:
                limit_mom = st.number_input(
                    "Rows to show", min_value=1, max_value=100, value=20, key="limit_tab3_mom"
                )
            with col_mom_title:
                st.subheader(f"📊 Top {limit_mom} Momentum Signals")

            if not mom_sig_df_all.empty:
                st.dataframe(
                    mom_sig_df_all.head(limit_mom),
                    column_config={
                        "Stock Name":   "Symbol",
                        "LTP":          st.column_config.NumberColumn("LTP",  format="₹ %.2f"),
                        "RSI":          st.column_config.NumberColumn("RSI (14)", format="%.1f"),
                        "Rel Strength": st.column_config.NumberColumn("Relative Strength (5-Period)", format="%.2f%%"),
                        "ADX":          st.column_config.NumberColumn("ADX",  format="%.1f"),
                        "is_squeeze":   "Prev Day Squeeze",
                    },
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("No momentum signatures found in this scan.")

        # ── Tab 4: Category Leaders & Super Signals ──────────────────
        with tab_leaders:
            st.markdown("### 🏆 Combined Super Signals & Category Leaders")
            col_ss, col_cats = st.columns(2)

            with col_ss:
                st.subheader("🔥 Super Signals")
                
                col_lim1, col_lim2 = st.columns(2)
                with col_lim1:
                    overlap_threshold = st.number_input(
                        "Min Overlap (1-4)", min_value=1, max_value=4, value=2, key="overlap_tab4"
                    )
                with col_lim2:
                    list_size = st.number_input(
                        "Rows to show", min_value=1, max_value=100, value=20, key="list_size_tab4"
                    )
                
                # Dynamic Super Signals calculation using local parameters
                combined_leaders = (
                    _top_names("Volume", list_size) + _top_names("Stoch RSI K", list_size)
                    + _top_names("SMI", list_size) + _top_names("MACD", list_size)
                )
                counts = Counter(combined_leaders)
                super_signals_records = []
                for stock, cnt in counts.items():
                    if cnt >= overlap_threshold:
                        row = unique_df[unique_df["Stock Name"] == stock].iloc[0]
                        super_signals_records.append({
                            "Stock Name": stock,
                            "LTP": row["LTP"],
                            "Appearances": cnt,
                            "Is Breakout": "🚀 Yes" if row["is_momentum_signature"] else "No",
                        })
                local_super_sig_df = (
                    pd.DataFrame(super_signals_records).sort_values(by="Appearances", ascending=False).head(list_size)
                    if super_signals_records else pd.DataFrame()
                )

                st.markdown(
                    f"*Stocks appearing in {overlap_threshold} or more top leaderboards "
                    f"(Volume · Trend/SMI · Momentum/RSI · MACD) based on Top {list_size} lists.*"
                )

                if not local_super_sig_df.empty:
                    st.dataframe(
                        local_super_sig_df,
                        column_config={
                            "Stock Name":  "Symbol",
                            "LTP":         st.column_config.NumberColumn("LTP", format="₹ %.2f"),
                            "Appearances": st.column_config.NumberColumn("List Occurrences", format="%d"),
                        },
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info("No super signal leaders found in this scan.")

            with col_cats:
                st.subheader("🏅 Categories")
                limit_cats = st.number_input(
                    "Rows to show", min_value=1, max_value=100, value=20, key="limit_tab4_cats"
                )
                with st.expander(f"📈 Top {limit_cats} SMI (Trend Strength)", expanded=True):
                    st.dataframe(
                        top_smi_df_all.head(limit_cats),
                        column_config={"LTP": st.column_config.NumberColumn("LTP", format="₹ %.2f")},
                        hide_index=True, width="stretch",
                    )
                with st.expander(f"💎 Top {limit_cats} Volume Leaders", expanded=False):
                    st.dataframe(
                        top_vol_df_all.head(limit_cats),
                        column_config={"LTP": st.column_config.NumberColumn("LTP", format="₹ %.2f")},
                        hide_index=True, width="stretch",
                    )
                with st.expander(f"⚡ Top {limit_cats} Stochastic RSI Leaders", expanded=False):
                    st.dataframe(
                        top_rsi_df_all.head(limit_cats),
                        column_config={"LTP": st.column_config.NumberColumn("LTP", format="₹ %.2f")},
                        hide_index=True, width="stretch",
                    )
                with st.expander(f"🔥 Top {limit_cats} MACD Leaders", expanded=False):
                    st.dataframe(
                        top_macd_df_all.head(limit_cats),
                        column_config={"LTP": st.column_config.NumberColumn("LTP", format="₹ %.2f")},
                        hide_index=True, width="stretch",
                    )

        # ── Tab 5: Intraday Winners ───────────────────────────────────
        with tab_winners:
            st.markdown("### 🎖️ Intraday Session Winners")
            st.markdown("*Stocks with session change > +0.3% since open — strong intraday momentum.*")
            col_win_title, col_win_opt = st.columns([3, 1])
            with col_win_opt:
                limit_winners = st.number_input(
                    "Rows to show", min_value=1, max_value=100, value=20, key="limit_tab5_winners"
                )
            with col_win_title:
                st.subheader(f"📊 Top {limit_winners} Intraday Winners")

            if not winners_df_all.empty:
                st.dataframe(
                    winners_df_all.head(limit_winners),
                    column_config={
                        "Stock Name": "Symbol",
                        "Change_Pct": st.column_config.NumberColumn("% Change from Open", format="%.2f%%"),
                        "LTP":        st.column_config.NumberColumn("LTP",  format="₹ %.2f"),
                        "VWAP":       st.column_config.NumberColumn("VWAP", format="₹ %.2f"),
                    },
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("No significant intraday gainers found in this scan.")

        # ── Action buttons ────────────────────────────────────────────
        st.markdown("---")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            csv = results_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Results (CSV)", csv,
                "results.csv", "text/csv", width="stretch",
            )
        with col_a2:
            if st.button("📤 Send to Telegram", width="stretch"):
                if send_to_telegram(results_df, selected_universe, selected_timeframe):
                    st.success("✅ Results sent to Telegram!")
                else:
                    st.error("❌ Failed to send to Telegram")

# ---------------------------------------------------------------------------
# SCORING EXPLANATION & STRATEGY GUIDE (always visible at the bottom)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 📊 Strategy Guide & Technical Calculations")

exp_entry, exp_prob, exp_advanced, exp_catch = st.tabs([
    "🎯 Scan Entry Criteria (Tier 1)",
    "⭐ Probability Score Models",
    "🚀 Advanced Signals (Tier 2)",
    "🔍 Catching Stocks Early",
])

with exp_entry:
    strat = config.STRATEGY_CONFIG
    st.markdown(f"""
    #### Tier 1: Base Selection (The Ticket to Entry)
    For a stock to be included in any scan results, it must satisfy all of the following base technical conditions simultaneously:

    | Indicator | Required Condition | Active Configuration | Description |
    |-----------|--------------------|----------------------|-------------|
    | **EMA Layers** | Price > EMA 5 AND Price > EMA 9 AND Price > EMA 21 | `> {', '.join(map(str, strat['EMA']))}` | Confirms a short-term upward-trending structure. |
    | **Stoch RSI** | Stoch RSI %K > {strat['STOCH_RSI_K_MIN']} | `> {strat['STOCH_RSI_K_MIN']}` | Ensures strong immediate bullish momentum. |
    | **SMI** | Stochastic Momentum Index > {strat['SMI_MIN']} | `> {strat['SMI_MIN']}` | Confirms mid-term trend strength is established. |
    | **MACD** | MACD Line > {strat['MACD_MIN']} | `> {strat['MACD_MIN']}` | Confirms active moving average convergence/divergence. |
    | **VWAP** | Price > VWAP (Intraday only) | `Price > VWAP` | Ensures positive intraday institutional accumulation. |
    """)

with exp_prob:
    st.markdown(r"""
    We calculate and compare two probability scoring methods on the dashboard:

    #### 1. Standard 3-Factor Model (Classic)
    $$\text{Score} = \text{Change Score (40)} + \text{SMI Score (30)} + \text{MACD Score (30)}$$

    | Factor | Weight | Logic |
    |--------|--------|-------|
    | **Change Score** | 40 pts | $\text{Clip}\!\left(\frac{\%\Delta}{5}, 0, 1\right) \times 40$ where $\%\Delta = \frac{\text{LTP}-\text{Open}}{\text{Open}} \times 100$ |
    | **SMI Score** | 30 pts | $\text{Clip}\!\left(\frac{\text{SMI}}{100}, 0, 1\right) \times 30$ |
    | **MACD Score** | 30 pts | $\text{Clip}\!\left(\frac{\text{MACD}}{5}, 0, 1\right) \times 30$ |

    **Limitation**: Pure absolute momentum — ranks all stocks highly during market-wide rallies (*beta trapping*).

    ---

    #### 2. Enhanced 5-Factor Model (V3 Institutional Model)
    $$\text{Score} = \text{Dynamic Change (30)} + \text{SMI Zone (20)} + \text{Normalized MACD (20)} + \text{RVOL (15)} + \text{Sharpe-RS (15)}$$

    | Factor | Weight | Logic |
    |--------|--------|-------|
    | **Dynamic Change** | 30 pts | $\text{Clip}\!\left(\frac{\%\Delta}{\text{ATR}\% \times 1.5}, -0.5, 1.0\right) \times 30$ where $\text{ATR}\% = \max\!\left(\frac{\text{ATR}_{14}}{\text{Open}} \times 100, 0.5\%\right)$ |
    | **SMI Zone** | 20 pts | **SMI 40–80 (Sweet Spot)**: 20 pts (inclusive) · **SMI ≥80 (Overbought Decay)**: 10 pts · **SMI <40**: 0 pts |
    | **Normalized MACD** | 20 pts | $\text{Clip}\!\left(\frac{\text{MACD}}{\text{ATR}_{14} \times 3}, 0, 1\right) \times 20$ (volatility-neutralized to eliminate price bias) |
    | **RVOL Score** | 15 pts | **≥1.5×**: 15 pts + breakout bonus $(RVOL-1.5) \times 2$ · **1.0–1.5×**: linear scale · **<1.0×**: penalty $(RVOL-1) \times 10$ (floored at -10) |
    | **Sharpe-RS** | 15 pts | $\text{Clip}\!\left(\frac{\text{Rel Strength}}{\sigma_{\text{effective}} \times 2.0}, 0, 1\right) \times 15$ where $\sigma_{\text{effective}} = \max(\sigma_{\text{daily\_returns}}, 0.5\%)$ |

    **Institutional logic**: Eliminates beta trapping via Nifty-relative RS, normalizes MACD and daily change using Wilder's ATR to remove price/volatility scale distortions, manages overbought oscillator decay, and uses volatility-adjusted Sharpe-RS rankings.
    """)

with exp_advanced:
    st.markdown(r"""
    #### 1. Momentum Signature (Gold Badge Breakout)
    A stock triggers a **Momentum Signature** when it simultaneously satisfies:

    | Criterion | Condition | Description |
    |-----------|-----------|-------------|
    | **Strict Trend** | Price > EMA 9 > EMA 21 > EMA 50 | Strong active trend alignment. |
    | **Momentum Confluence** | RSI > 60 AND MACD Histogram > 0 | Confirms acceleration in price speed and volume spread. |
    | **Launchpad (Squeeze)** | Prev day BBW ≤ 0.05 AND current ADX > 20 | Volatility compression breakout with trend strength. |
    | **Trigger** | Volume > 2× avg AND Price > Prev Day High AND Rel Strength > -0.1 AND Price > ORB30 High | High-volume breakout confirming immediate demand. |

    #### 2. Multi-Category Leaders (Super Signals)
    $$\text{Super} = \{ S \mid \text{Count}(S \in \text{Top Vol} \cup \text{Top RSI} \cup \text{Top SMI} \cup \text{Top MACD}) \ge 2 \}$$
    Stocks appearing in **at least 2** category leaderboards simultaneously.

    #### 3. Intraday Winners
    All signals with session change $\Delta > +0.3\%$ relative to the session open price.
    """)

with exp_catch:
    st.markdown("""
    #### How to Catch Stocks Before They Reach the Top Probability List

    Look for these early-warning signals **before** a stock appears in the top-10:

    1. **Bollinger Band Squeezes (`is_squeeze` = True)**
       - BBW ≤ 0.05 → bands contracted under 5%. Volatility compression precedes explosive trends.

    2. **ADX Turning Up (> 20)**
       - Rising ADX above 20 signals a trend forming out of consolidation.

    3. **MACD Hist Crossing Zero (positive while MACD line still negative)**
       - Bullish divergence — momentum turning before the price breakout.

    4. **Price Crossing Above VWAP**
       - Clean intraday breakout above VWAP indicates institutional accumulation beginning.
    """)

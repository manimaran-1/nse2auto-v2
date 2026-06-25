# 🚀 Ultimate Project Blueprint: Automated Trading Scanner & Deployment Suite

Use the content below as your **master prompt** whenever you want to build a new professional, background-automated trading scanner.

---

### 📋 THE COMPLETE TRADING SCANNER BLUEPRINT (MASTER PROMPT)

**Objective**:
Build a professional, automated Python trading scanner that runs locally on my machine. The scanner will pull data from Yahoo Finance (`yfinance`), process a specific technical indicator (derived from a PineScript I will provide), and send buy/sell signals to a Telegram channel. The project must have a modular architecture, robust state management, a clean Streamlit dashboard, and professional-grade Telegram reporting.

---

**Phase 1: Project Architecture (Exactly 8 Files)**
Project Name: `utbot_auto` (or current project name). Files must include:
1. `config.py`: Environment variables (`.env`), constants, IST timezone setup, and stock universes. Must export `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
2. `data_loader.py`: Handles `yfinance` fetching with exponential backoff and retry logic (up to 3 attempts) on network or rate-limit failures (HTTP 429). Fetches NSE universe lists live from NSE archives.
3. `indicators.py`: Contains the 1:1 mathematical translation of the PineScript indicator into Python/NumPy logic. Also includes advanced indicators: `StochRSI`, `SMI (Stochastic Momentum Index)`, `Bollinger Bands`, `MACD`, `VWAP`, `ADX`, and multi-period `EMA`.
4. `scanner.py`: The core asynchronous loop using `asyncio` with a 10-worker `asyncio.Semaphore` and `asyncio.to_thread` for non-blocking `yfinance` calls. Aggregates signals, computes 10-point probability scores, and assigns momentum categories.
5. `reporter.py`: Telegram reporting engine using the `TelegramReporter` class (no global functions). Delivers structured plain-text messages with CSV-first delivery and intelligent message splitting.
6. `app.py`: A Streamlit dashboard for real-time monitoring, manual triggering, live progress animation, momentum heatmap, and strategy documentation.
7. `app_headless.py`: A script for CRON or systemd execution without the UI.
8. `requirements.txt`: Pinned dependencies for reproducible installs.

---

**Phase 2: Mathematical Parity & Indicator Rules**
- **Timezone**: ALL data fetching and Telegram reporting MUST be localized to Indian Standard Time (IST, `Asia/Kolkata`).
- **Data Source**: Use `yfinance` to fetch NSE data. Append `.NS` to symbols.
- **Parity Engine**: Do NOT use heavy wrappers. Implement logic bar-by-bar (using `for` loops on NumPy arrays) if the PineScript uses `var` states or recursive calculations to ensure 100% TradingView parity.
- **Signal Key**: Return a dictionary per stock with keys: `symbol`, `signal`, `price`, `ltp`, `time`, `score`, `momentum_category`, `change`.

---

**Phase 3: Automation & Deployment Suite**
Create these 5 Bash scripts to manage the full bot lifecycle:
1. `run_localhost.sh`: Interactive runner with `venv` auto-setup, dependency sync, and a menu for Dashboard/Bot/Test.
2. `setup_service.sh`: One-click installer for a **systemd user service** (`~/.config/systemd/user/`) for 24/7 background operation.
3. `utbot_auto.service`: The systemd service definition template (Restart=always).
4. `restart_service.sh`: Quick shortcut to restart the background process.
5. `remove_service.sh`: Complete uninstaller for the systemd service.

---

**Phase 4: Performance & Concurrency**
- **10 Simultaneous Workers**: Use `asyncio.Semaphore(10)` — this is the optimal balance for speed vs `yfinance` rate limits.
- **Non-Blocking IO**: Use `asyncio.to_thread(fetch_data, symbol, interval)` so that `yfinance` network calls never block the event loop.
- **Live Progress**: During scanning, display a live terminal progress line: `[042/500] Fetching RELIANCE.NS`. In the Streamlit dashboard, mirror this with a `st.progress` bar and `st.empty()` status text showing `Fetching X/Y stocks...`.
- **Retry with Exponential Backoff**: In `data_loader.py`, implement a retry loop with `time.sleep(2 ** attempt)` to handle transient HTTP 429 and connection errors.

---

**Phase 5: 10-Point Probability Scoring System**
Every signal must be evaluated against a 10-point technical checklist. The score is stored in the `score` field of the signal dictionary.

| Score | Criteria | Technical Logic |
|:------|:---------|:----------------|
| **1 pt** | Price vs EMA 5 | `close > ema(close, 5)` |
| **1 pt** | Price vs EMA 9 | `close > ema(close, 9)` |
| **1 pt** | Price vs EMA 21 | `close > ema(close, 21)` |
| **1 pt** | StochRSI Overbought | `stoch_k > 70` |
| **1 pt** | SMI Positive | `smi > 30` |
| **1 pt** | EMA Stack Alignment | `ema9 > ema21 > ema50` |
| **1 pt** | Momentum Signature | `rsi > 60 AND macd_hist > 0` |
| **1 pt** | Trend Strength | `adx > 20` |
| **1 pt** | Volume Surge | `volume > 1.5x avg volume (20-period)` |
| **1 pt** | VWAP Alignment | `close > vwap` |

---

**Phase 6: Momentum Breakout Categories**
Assign every scanned stock a `momentum_category` (stored as a string). Categories are determined with these exact conditions:

- **`Diamond`** — Ultra high conviction: `RSI > 65 AND close > upper_bb AND ema21 > ema50 > ema200 AND adx > 20`
- **`Golden`** — High probability trend: `60 <= RSI <= 70 AND ema21 > ema50 > ema200 AND adx > 15`
- **`Euphoria`** — Extreme momentum: `RSI > 70 AND close > upper_bb AND adx > 25`
- **`Neutral`** — Default for all other signals

---

**Phase 7: Telegram Reporting (TelegramReporter Class)**
Implement a `TelegramReporter` class in `reporter.py` with these methods:

1. **`_send_msg(text)`**: Sends plain text. If text exceeds 4000 characters, automatically split into chunks before sending. **No Markdown or MarkdownV2 formatting** — plain text only for 100% delivery reliability.

2. **`send_csv(df, scan_name, caption="")`**: Sends the full results DataFrame as a `.csv` file. Implement a **3-attempt retry loop** with a 2-second sleep between attempts to handle `Connection Reset` or timeout network errors. The caption should include the scan header.

3. **`send_batch_report(df, scan_name)`**: The main orchestration method. Workflow:
   - Parse `time` column into a `time_dt` datetime column.
   - Detect `max_date = df['time_dt'].dt.date.max()` — the **Last Active Market Day**.
   - Create `summary_df` filtered to only `max_date`. All text sections below use this filtered set.
   - Sort `summary_df` by `time_dt` descending (**Most Recent First** in all sections).
   - **Step 1**: Call `send_csv(df, ...)` first with the scan header as caption. The CSV contains the **full unfiltered** history.
   - **Step 2**: Send `🟢 BUY SIGNALS (N)` section.
   - **Step 3**: Send `🔴 SELL SIGNALS (N)` section.
   - **Step 4**: Send `🎯 TOP 10 PROBABILITY TRADES` section — sorted by `score DESC, time_dt DESC`.
   - **Step 5**: Send `📊 CATEGORY BREAKDOWN` section — three sub-groups: `💎 DIAMOND`, `⚡ GOLDEN`, `🔥 EUPHORIA`.

**Signal Line Format** (for every stock in every section):
```
• SYMBOL @ LTP | DD/MM HH:MM | Score: X/10
```

**Report Header** (used as CSV caption):
```
🔍 SCAN: {scan_name}
📅 Market Date: YYYY-MM-DD
🕒 Run Time: HH:MM AM/PM
=========================
```

---

**Phase 8: Streamlit Dashboard (`app.py`)**
- **Live Progress**: Use `st.status()`, `st.progress()`, and `st.empty()` to show `Fetching X/Y stocks...` during the scan.
- **Momentum Heatmap**: After scan completes, display the top 12 signals as colored tile cards in a 4-column grid. Color by category:
  - Diamond: Blue-teal gradient (`#0891b2`)
  - Golden: Orange-brown gradient (`#b45309`)
  - Euphoria: Red gradient (`#991b1b`)
  - Default: Green gradient (`#065f46`)
- **Detailed Signal Table**: Use `st.dataframe()` with `style.map()` to color-code BUY (green) and SELL (red) rows. Color `score` column: red < 5, yellow 5-7, green >= 7.
- **Strategy Guide**: Add a collapsible `st.expander("📖 Strategy & Scoring Logic Guide")` at the bottom of the page documenting the PineScript logic, the 10-point scoring criteria, and all 3 momentum category definitions in a markdown table.
- **High Contrast UI**: Inject custom CSS via `st.markdown(..., unsafe_allow_html=True)` to force white text on all metric cards and heatmap elements for readability in dark mode.

---

**Phase 9: Robustness & Signal Logic**
- **Error Handling**: Implement strict exception handling (catching `yfinance` timeouts, bad ticker data, or empty DataFrames). Return `None` from the worker task and filter these out before reporting.
- **Signal Logic**: Focus on **Crossover Detection (State Parity)** within `indicators.py`. By comparing the current state to the previous state, ensure only the most recent "true" signal changes are captured.
- **No External Deduplication**: Rely on the accuracy of the historical data and state-logic rather than persistent database logs for signal deduplication.

---

**Initial Task for You (The AI)**:
1. Acknowledge this comprehensive blueprint.
2. Ask me for these required inputs:
   - The **PineScript Code** to be translated.
   - The **Target Universe** of stocks (e.g., Nifty 50, Nifty 500).
   - The desired **Timeframe** (e.g., 5m, 1h, 1d).
   - **Telegram Bot Token & Chat ID** (for `.env`).
3. **STOP** and do not generate any Python code until I have provided the PineScript and credentials.

### 📋 STOP COPYING HERE

---

## 🛠️ Developer Implementation Tips

### Performance
- **10-Worker Semaphore**: `asyncio.Semaphore(10)` is the proven sweet spot for `yfinance` without triggering rate limits.
- **Progress Carriage Return**: Use `print(f"\r[{count:03d}/{total:03d}] Fetching {symbol:<15}", end="", flush=True)` for a clean terminal progress line.
- **Venv Tracking**: In `run_localhost.sh`, use a `venv/.installed` marker file to avoid redundant `pip install` commands on every launch.

### Telegram Reliability
- **No Markdown**: Use plain text only. MarkdownV2 is fragile with stock symbols like `M&M.NS`. It silently fails and sends no message.
- **CSV First**: Always send the CSV document before the text summaries so the data is available immediately even if text sending fails.
- **Retry on CSV**: Network resets on large file uploads are common. Always wrap `sendDocument` in a 3-attempt retry with `time.sleep(2)`.
- **Message Splitting**: Always chunk text into ≤4000 character pieces before calling `sendMessage`.

### Signal Data
- **Market Day Filter**: Text summaries must show only the **most recent market date** found in the data. The CSV contains full history. This prevents stale old signals from cluttering fresh reports.
- **Timestamps**: Always display signal time as `DD/MM HH:MM` in Telegram messages for compact readability.
- **Sort All Lists**: Every section in the Telegram report (Buys, Sells, Probability, Categories) must be sorted by `time_dt` descending so the newest signals are at the top.

### Code Structure
- **Thread Safety**: Ensure data fetching is thread-safe. By using `yf.set_tz_cache(False)`, the project avoids internal file-locking issues during multi-threaded scans.
- **Systemd User Mode**: Always favor `systemctl --user` to ensure the bot runs without requiring root/sudo permissions.
- **Key Consistency**: The signal dictionary key for the momentum phase must be `momentum_category` (not `category`) — used consistently in `scanner.py`, `reporter.py`, and `app.py`.

---

## 🔟 Phase 10: CI/CD, GitHub Actions & Cron Deployment (Plug & Play)

> **This section is a reusable, plug-and-play template.** Copy it into any new scanner project to get instant GitHub Actions automation and local cron scheduling.

### 10.1 — Repository Hygiene: `.gitignore`

Every scanner project MUST have a `.gitignore` that excludes:
```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
venv/

# Environment & Secrets
.env

# Project Cache & Logs
cache/
*.txt
!requirements.txt
!instructions.md
cron.log

# Streamlit
.streamlit/
```

> **Rule**: NEVER push `.env` files containing `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` to a public repository. Use GitHub Secrets for CI/CD and local `.env` for localhost.

---

### 10.2 — GitHub Actions Workflow (`market_scan.yml`)

Place this file at `.github/workflows/market_scan.yml`:

```yaml
name: NSE Market Scanner

on:
  schedule:
    # Cron runs in UTC. Convert IST to UTC by subtracting 5:30.
    # 9:16 AM IST = 3:46 UTC | 3:16 PM IST = 9:46 UTC
    - cron: '46 3-9 * * 1-5'
  workflow_dispatch: # Allows manual trigger from GitHub UI

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Market Scan
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          SCAN_UNIVERSE: ${{ vars.SCAN_UNIVERSE || 'Nifty 500' }}
          SCAN_INTERVAL: ${{ vars.SCAN_INTERVAL || '1h' }}
          SEND_IF_EMPTY: ${{ vars.SEND_IF_EMPTY || 'True' }}
        run: |
          python automation_bot.py
```

#### ⚠️ Critical GitHub Actions Rules
| Rule | Detail |
|:-----|:-------|
| **Single quotes in expressions** | `${{ vars.X \|\| 'default' }}` — use single quotes, NEVER double quotes inside `${{ }}`. Double quotes cause `Unexpected symbol` parse errors. |
| **Secrets setup** | Go to **Settings > Secrets and variables > Actions** and add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as **Repository Secrets**. |
| **Variables setup** | Optionally add `SCAN_UNIVERSE`, `SCAN_INTERVAL`, `SEND_IF_EMPTY` as **Repository Variables** to override defaults without code changes. |
| **UTC cron** | GitHub Actions cron uses UTC. IST = UTC + 5:30. Always convert your IST schedule to UTC before writing the cron expression. |
| **204 No Content** | A `204` response from `workflow_dispatch` means **success** (workflow queued). It is NOT an error. |

---

### 10.3 — Clean Push Script (`clean_push.sh`)

A reusable script to force-push a fresh copy of the project to GitHub (useful after major refactors or repo migrations):

```bash
#!/bin/bash
REPO_URL="https://github.com/YOUR_USER/YOUR_REPO.git"

echo "🧹 Starting a Fresh Git Push..."
rm -rf .git
git init
git branch -M main
git remote add origin "$REPO_URL"
git add .
git commit -m "Fresh Clean Start: Scanner Deployment"
echo "🚀 Pushing to GitHub..."
git push -u origin main --force
```

> **Usage**: Update `REPO_URL` and run `bash clean_push.sh`. You will be prompted for your GitHub Personal Access Token (PAT) as the password.

---

### 10.4 — Local Cron Scheduling

For running the scanner on your own machine (instead of or alongside GitHub Actions):

**Step 1: Create Virtual Environment**
```bash
cd /path/to/your/scanner/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Step 2: Ensure Trigger Script is Executable**
```bash
chmod +x trigger_now.sh
```

**Step 3: Add Crontab Entry**
```bash
# Runs at minute :16 of every hour from 9 AM to 3 PM IST, Mon-Fri
(crontab -l 2>/dev/null; echo "16 9-15 * * 1-5 /absolute/path/to/trigger_now.sh >> /absolute/path/to/cron.log 2>&1") | crontab -
```

**Step 4: Verify**
```bash
crontab -l
```

#### Trigger Script Template (`trigger_now.sh`)
```bash
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
source venv/bin/activate
export TEST_RUN=1
export ONCE=1
python3 automation_bot.py
```

> **Rule**: Always use **absolute paths** in crontab entries. Cron does not inherit your shell's `$PATH` or working directory.

---

## 1️⃣1️⃣ Phase 11: Session Changelog — Bugs Fixed & Features Added

> **Date**: 2026-04-20 | **Project**: `nse2_automation` → `nse2auto`

### 🐛 Bugs Fixed

| # | Bug | Root Cause | Fix Applied |
|:--|:----|:-----------|:------------|
| 1 | **GitHub Action YAML parse error** — `Unexpected symbol: '"Nifty'` when triggering `workflow_dispatch` | Double quotes (`"Nifty 500"`) used inside `${{ }}` expressions. GitHub Actions expressions only accept single quotes. | Changed all default values to single quotes: `${{ vars.SCAN_UNIVERSE \|\| 'Nifty 500' }}` |
| 2 | **GitHub Action silent failure** — Scanner triggered (204 OK) but no Telegram messages sent | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` were only in local `.env`, not configured as GitHub repository Secrets | Guided user to add both tokens under **Settings > Secrets and variables > Actions** |
| 3 | **Sensitive `.env` pushed to public repo** — Telegram tokens and Chat IDs exposed on GitHub | No `.gitignore` file existed in the project | Created comprehensive `.gitignore` excluding `.env`, `__pycache__/`, `cache/`, `.streamlit/`, and temp `.txt` files |
| 4 | **Telegram 404 Client Error** — URL corrupted with `%0A` | Telegram tokens copied from GitHub Secrets often contain a hidden newline character | Applied `.strip()` to `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `config.py` |
| 5 | **Database/File Locking error** — Scanner crashes during fetch | Multi-threaded `yfinance` calls competing for the same internal cache file | Added `yf.set_tz_cache(False)` in `data_loader.py` to disable global caching and ensure zero-database operation |

### ✨ Features Implemented

| # | Feature | Description |
|:--|:--------|:------------|
| 1 | **Repository migration** | Migrated project from `nsetg.git` → `nse2auto.git`. Updated `clean_push.sh` with new `REPO_URL` and performed clean force-push. |
| 2 | **Virtual environment setup** | Created `venv` and installed all dependencies from `requirements.txt` (pandas, yfinance, streamlit, requests, etc.) |
| 3 | **Local cron job configuration** | Provided exact `crontab` entry for market-hours scheduling: `16 9-15 * * 1-5` (Mon-Fri, hourly at :16) |
| 4 | **Manual test run verification** | Executed `trigger_now.sh` end-to-end — successfully scanned Nifty 500 and sent **128 signals** to Telegram |
| 5 | **GitHub Actions workflow fix** | Fixed YAML syntax for `market_scan.yml` to enable `workflow_dispatch` manual triggers and scheduled cron runs |
| 6 | **10-Point Probability Engine** | Implemented a weighted scoring system based on EMA alignment, momentum, and volume. |
| 7 | **Momentum Classification** | Added "Diamond", "Golden", and "Euphoria" labels to identify the highest conviction trades. |

---

## 🚀 Phase 12: The "Plug & Play" Universal Stability Prompt

> **Copy-paste this addition into your prompt whenever building a new scanner to ensure it's "Production Ready" from Day 1.**

**Universal Stability Requirements**:
1. **Secret Hardening**: In `config.py`, ALWAYS apply `.strip()` to `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. GitHub Secrets often inject hidden newlines that cause 404 errors.
2. **Concurrency Safety**: In `data_loader.py`, ALWAYS call `yf.set_tz_cache(False)` at the top of the file. This ensures a database-free architecture and prevents file-lock errors when running multi-threaded scans.
3. **Timezone Parity**: Ensure every script (`app.py`, `automation_bot.py`, `scanner.py`) uses `pytz.timezone('Asia/Kolkata')` for all datetime objects and display strings.
4. **Resilient CSV Delivery**: Telegram text messages are fragile. The bot must ALWAYS send the CSV file first, wrapped in a retry loop, to ensure data is delivered even if text formatting or length causes a failure.
5. **Zero-Config Deployment**: Include a `trigger_now.sh` that automatically detects its own directory path and uses the absolute path to the virtual environment, making it "plug-and-play" for crontab without manual environment setup.

import time
import os
import pytz
import logging
from datetime import datetime
import pandas as pd
import requests
import scanner
import data_loader
import config
import reporter
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuration for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Secure Configuration from Secrets / Env Vars
BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
CHAT_ID = config.TELEGRAM_CHAT_ID
SCAN_UNIVERSE = config.SCAN_UNIVERSE
SCAN_INTERVAL = config.SCAN_INTERVAL
SEND_IF_EMPTY = config.SEND_IF_EMPTY
LIVE_UNIVERSE_FETCH = config.LIVE_UNIVERSE_FETCH
SEND_CSV = config.SEND_CSV
ENABLE_INST_FILTERS = config.ENABLE_INST_FILTERS
INST_MIN_TURNOVER_CRORES = config.INST_MIN_TURNOVER_CRORES
INST_MIN_LISTING_AGE_DAYS = config.INST_MIN_LISTING_AGE_DAYS
INST_REGIME_FILTER = config.INST_REGIME_FILTER
MAX_WORKERS = config.MAX_WORKERS



def validate_config():
    """Ensure all required configuration is present."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("🛑 CRITICAL: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")
        return False
    return True

def send_telegram_message(message):
    """Sends a text message via Telegram Bot API with fallback on Markdown parse errors."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning(f"Failed to send Telegram message with Markdown: {e}. Retrying as plain text...")
        payload.pop("parse_mode", None)
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as retry_err:
            logger.error(f"Error sending plain text message to Telegram: {retry_err}")

def send_telegram_document(file_path, caption):
    """Sends a document (CSV) via Telegram Bot API with fallback on Markdown parse errors."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
            response = requests.post(url, files=files, data=data, timeout=20)
            if response.status_code != 200:
                logger.warning(f"Telegram API Error (sendDocument Markdown): {response.status_code} - {response.text}. Retrying without parse_mode...")
                doc.seek(0)
                data.pop('parse_mode', None)
                response = requests.post(url, files=files, data=data, timeout=20)
                if response.status_code != 200:
                    logger.error(f"Telegram API Error (sendDocument plain text): {response.status_code} - {response.text}")
                    return False
            return True
    except Exception as e:
        logger.error(f"Error sending document to Telegram: {e}")
        return False

def run_scan():
    """Executes the stock scan and sends results to Telegram."""
    now = datetime.now(IST)
    
    # Market Open Sync Guard
    if now.hour == 9 and 15 <= now.minute < 16:
        logger.info("Market just opened. Waiting 60s for data synchronization...")
        time.sleep(60)
        now = datetime.now(IST)
        
    logger.info(f"Starting Scan: {SCAN_UNIVERSE} ({SCAN_INTERVAL})")
    
    try:
        # Resolve symbols using LIVE_UNIVERSE_FETCH configuration
        if SCAN_UNIVERSE == "Nifty 500":
            symbols = data_loader.get_nifty500_symbols(live_fetch=LIVE_UNIVERSE_FETCH)
        elif SCAN_UNIVERSE == "Nifty 200":
            symbols = data_loader.get_nifty200_symbols(live_fetch=LIVE_UNIVERSE_FETCH)
        else:
            symbols = data_loader.get_index_constituents(SCAN_UNIVERSE, live_fetch=LIVE_UNIVERSE_FETCH)
        
        if not symbols:
            logger.warning(f"No symbols found for {SCAN_UNIVERSE}. Aborting scan.")
            return

        send_telegram_message(f"🚀 *NSE Scanner v2 Dual Method* | 🔍 *Started*\n📊 *Universe:* {SCAN_UNIVERSE} ({SCAN_INTERVAL})\nScanning {len(symbols)} symbols...")
        
        # Execute scanner
        results_df = scanner.scan_market(
            symbols, 
            interval=SCAN_INTERVAL,
            enable_inst_filters=ENABLE_INST_FILTERS,
            min_turnover_crores=INST_MIN_TURNOVER_CRORES,
            min_age_days=INST_MIN_LISTING_AGE_DAYS,
            regime_filter=INST_REGIME_FILTER,
            max_workers=MAX_WORKERS
        )
        
        if not results_df.empty:
            datasets = []
            if SCAN_UNIVERSE in ["Nifty 500", "Nifty 200", "Nifty 50", "Nifty Bank", "Nifty IT", "Nifty PSU Bank", "Nifty Private Bank", "Nifty 100", "Nifty Next 50"]:
                # If we're scanning a universe that's already a subset of Nifty 500, don't split
                datasets.append((results_df, SCAN_UNIVERSE, 20))
            else:
                # We are scanning Total Cash Segment or another large universe
                cat_to_symbols = data_loader.get_all_categories_and_symbols()
                covered_stocks = set()
                
                # Prioritize standard indexes so they appear first in the reports list
                priorities = {'50': 0, 'Next 50': 1, '100': 2, '200': 3, 'nse500': 4, 'mid': 5, 'small': 6}
                sorted_cats = sorted(cat_to_symbols.keys(), key=lambda c: (priorities.get(c, 99), c))
                
                for cat in sorted_cats:
                    cat_symbols = cat_to_symbols[cat]
                    cat_df = results_df[results_df['Stock Name'].isin(cat_symbols)]
                    if not cat_df.empty:
                        # User-friendly label formatting
                        if cat == '50':
                            lbl = "Nifty 50"
                        elif cat == 'Next 50':
                            lbl = "Nifty Next 50"
                        elif cat == '100':
                            lbl = "Nifty 100"
                        elif cat == '200':
                            lbl = "Nifty 200"
                        elif cat == 'nse500':
                            lbl = "Nifty 500"
                        elif cat == 'mid':
                            lbl = "Nifty Midcap"
                        elif cat == 'small':
                            lbl = "Nifty Smallcap"
                        else:
                            display_cat = "IT" if cat.upper() == "IT" else cat
                            lbl = f"Nifty {display_cat}"
                        
                        datasets.append((cat_df, lbl, 10))
                        covered_stocks.update(cat_df['Stock Name'].tolist())
                
                # Any stock not in any category goes to "Other Cash Segment"
                other_df = results_df[~results_df['Stock Name'].isin(covered_stocks)]
                if not other_df.empty:
                    datasets.append((other_df, "Other Cash Segment", 10))
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            for df_subset, universe_label, limit in datasets:
                df_subset = df_subset.sort_values(by='Signal Time', ascending=False)
                # Sanitize filename
                safe_label = universe_label.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
                filename = f"scan_results_{safe_label}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
                file_path = os.path.join(base_dir, filename)
                
                df_subset.to_csv(file_path, index=False)
                
                # Generate Multi-Part Analysis Report
                report_parts = reporter.generate_report(df_subset, universe_label, SCAN_INTERVAL, limit=limit)
                
                # Send first part (with CSV if enabled, or as text if disabled)
                if report_parts:
                    if SEND_CSV:
                        caption = report_parts[0]
                        success = send_telegram_document(file_path, caption)
                        
                        if not success:
                            logger.warning("Caption upload failed. Triggering failsafe delivery...")
                            simple_title = f"📊 Scan Results: {universe_label} ({now.strftime('%H:%M')})"
                            send_telegram_document(file_path, simple_title)
                            send_telegram_message(caption)
                    else:
                        send_telegram_message(report_parts[0])
                    
                    # Send remaining parts as follow-up messages
                    for part in report_parts[1:]:
                        send_telegram_message(part)
                
                # Cleanup
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            logger.info(f"Results sent to Telegram: {len(results_df)} signals.")
        else:
            if SEND_IF_EMPTY:
                msg = (
                    f"🚀 *NSE Scanner v2 Dual Method*\n"
                    f"📊 *Universe:* {SCAN_UNIVERSE}\n"
                    f"⏰ *Timeframe:* {SCAN_INTERVAL}\n"
                    f"⚠️ No matches found at this time."
                )
                send_telegram_message(msg)
            logger.info("Scan complete - 0 signals found.")
                
    except Exception as e:
        logger.exception(f"Unexpected error in run_scan: {e}")
        send_telegram_message(f"❌ *Scanner Error:* {str(e)}")

def start_trigger_server():
    trigger_port = config.TRIGGER_PORT

    class TriggerHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.info(f"HTTP Trigger Request: {args[0]} - {args[1]}")

        def do_GET(self):
            if self.path == '/trigger':
                logger.info("External HTTP trigger received via GET /trigger. Initiating scan...")
                threading.Thread(target=run_scan).start()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success", "message": "Market scan triggered"}')
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Not Found"}')

        def do_POST(self):
            if self.path == '/trigger':
                logger.info("External HTTP trigger received via POST /trigger. Initiating scan...")
                threading.Thread(target=run_scan).start()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success", "message": "Market scan triggered"}')
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Not Found"}')

    def serve():
        try:
            server = HTTPServer(('0.0.0.0', trigger_port), TriggerHandler)
            logger.info(f"🚀 Trigger Server listening on http://0.0.0.0:{trigger_port}/trigger")
            server.serve_forever()
        except Exception as e:
            logger.error(f"Trigger Server error: {e}")

    t = threading.Thread(target=serve, daemon=True)
    t.start()

def main():
    if not validate_config():
        logger.error("Configuration validation failed. Exiting.")
        return

    # Start trigger server for VPS/cron-job.org HTTP webhook support
    if os.environ.get("GITHUB_ACTIONS") != "true" and os.environ.get("ONCE") != "1":
        start_trigger_server()

    logger.info("========================================")
    logger.info(" NSE Stock Scanner 2.0 - Automation Bot ")
    logger.info("========================================")
    logger.info(f"Universe: {SCAN_UNIVERSE} | Interval: {SCAN_INTERVAL} | Live Universe Fetch: {LIVE_UNIVERSE_FETCH}")
    
    # Check for immediate run
    if os.environ.get("TEST_RUN") == "1" or os.environ.get("GITHUB_ACTIONS") == "true":
        logger.info("Triggering initial scan (TEST_RUN/CI)...")
        run_scan()
        if os.environ.get("ONCE") == "1" or os.environ.get("GITHUB_ACTIONS") == "true":
            return

    # Specific Schedule: 9:16, 10:16, ..., 15:16 (3:16 PM)
    SCHEDULED_HOURS = [9, 10, 11, 12, 13, 14, 15]
    SCHEDULE_MINUTE = 16
    
    last_run_id = None # Format: "YYYY-MM-DD-HH"

    while True:
        try:
            now = datetime.now(IST)
            is_weekday = now.weekday() < 5 # 0=Mon, 4=Fri
            
            if is_weekday:
                current_run_id = now.strftime("%Y-%m-%d-%H")
                
                # Check if current hour and minute match our target
                if now.hour in SCHEDULED_HOURS and now.minute == SCHEDULE_MINUTE:
                    if last_run_id != current_run_id:
                        logger.info(f"Target time reached: {now.strftime('%H:%M')}. Starting scheduled scan.")
                        run_scan()
                        last_run_id = current_run_id
                
                # Close message/reset at end of day
                elif now.hour == 15 and now.minute > SCHEDULE_MINUTE and last_run_id == current_run_id:
                    logger.info("Market session processing complete for today.")
                    last_run_id = f"{current_run_id}-CLOSED" # Prevent re-trigger if restarted
                    
            # Daily reset for last_run_id if needed (though current_run_id handles it)
            if now.hour == 0 and now.minute == 0:
                last_run_id = None
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)
            
        time.sleep(30)

if __name__ == "__main__":
    main()

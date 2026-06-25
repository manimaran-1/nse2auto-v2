# NSE Market Bot Automation Walkthrough

I have implemented the precise scheduling and persistence you requested for your NSE scanner. The bot now triggers exactly at **9:16, 10:16, ..., 15:16** IST, Monday through Friday.

## ✅ Changes Made

### 1. Robust Scheduling Logic
Modified [automation_bot.py](automation_bot.py) to:
- Use a `last_run_id` tracker to ensure each scheduled hour triggers exactly once.
- Strictly adhere to the **9:16 AM – 3:16 PM** window.
- Automatically handles market holidays or weekends.

### 2. Local PC Persistence (systemd)
Created a standard Linux background service setup:
- [nsemarketbot.service](nsemarketbot.service): Service definition using your local venv.
- [setup_service.sh](setup_service.sh): One-click installer to start the bot in the background.
- [remove_service.sh](remove_service.sh): One-click uninstaller.

### 3. GitHub Actions Support
- Verified that the code automatically detects GitHub environments and runs as a single-scan job.
- **Bonus:** Created [.github/workflows/market_scan.yml](.github/workflows/market_scan.yml) with a cron matching your 9:16-15:16 IST schedule.

---

## 🛠️ How to use (Local PC)

### To Start the Bot:
Open your terminal and run:
```bash
./setup_service.sh
```
This will start the bot in the background. It will survive terminal closes and reboots.

### To Check if it's Running:
```bash
systemctl --user status nsemarketbot
```

### To Uninstall/Stop:
```bash
./remove_service.sh
```

---

## 🚀 GitHub Actions Setup
The code is already compatible. If you host this on GitHub:
1. Go to your repo **Settings > Secrets and variables > Actions**.
2. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Secrets.
3. The included workflow file will handle the rest!

> [!NOTE]
> GitHub Actions cron jobs can sometimes be delayed by 10-20 minutes. For **precise 9:16 AM timing**, running it on your local PC with the provided `setup_service.sh` is recommended.

---

## 🧪 Verification Results
- **Logic Check:** Verified triggers for 9:16, 10:16, and 15:16 with a mock test script. [PASSED]
- **Timezone Safety:** Confirmed it uses `Asia/Kolkata` (IST) regardless of host time. [PASSED]

---

## 🔗 Cron-Job.org Trigger Configuration Guide

You can trigger scans automatically using [cron-job.org](https://cron-job.org) through two different architectures:

### 1. Triggering via GitHub Actions (Serverless Cloud Setup)
If your repository is hosted on GitHub, you can configure `cron-job.org` to trigger your GitHub Actions workflow externally using a `repository_dispatch` event:

1. **Get a GitHub Personal Access Token (PAT)**:
   - Go to GitHub -> **Settings** -> **Developer Settings** -> **Personal Access Tokens** -> **Fine-grained tokens** (or Tokens Classic).
   - Generate a token with write access to your repository's **Contents** (to trigger `repository_dispatch` events).
2. **Configure cron-job.org**:
   - Create a new cron job.
   - **URL**: `https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches`
   - **Request Method**: `POST`
   - **HTTP Headers**:
     * `Accept`: `application/vnd.github+json`
     * `Authorization`: `Bearer YOUR_GITHUB_PERSONAL_ACCESS_TOKEN`
     * `User-Agent`: `cron-job-org`
   - **Request Body (JSON)**:
     ```json
     { "event_type": "trigger-scan" }
     ```
   - **Schedule**: Set to the desired scan timings (e.g. Monday-Friday at 9:16 AM, 10:16 AM, etc. in your preferred timezone).

---

### 2. Triggering via Local/VPS Webhook (Self-Hosted Setup)
When running the `automation_bot.py` locally or on a cloud virtual private server (VPS), a background HTTP daemon listens on port `8503` (customisable via `TRIGGER_PORT` in your env / `.env` file).

1. **Expose the Webhook Port**:
   - Ensure port `8503` is allowed through your VPS/router firewall (e.g. `ufw allow 8503`).
2. **Configure cron-job.org**:
   - Create a new cron job.
   - **URL**: `http://YOUR_VPS_PUBLIC_IP:8503/trigger`
   - **Request Method**: `GET` (or `POST`)
   - **Schedule**: Configure to target your required IST schedule (9:16 AM, 10:16 AM, ..., 3:16 PM).
   - Once hit, the server responds immediately with `{"status": "success"}` and starts the scan in a background thread.


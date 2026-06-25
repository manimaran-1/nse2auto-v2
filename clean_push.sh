#!/bin/bash

# Configuration: Your GitHub Repo URL
REPO_URL="https://github.com/manimaran-1/nse2auto.git"

echo "🧹 Starting a Fresh Git Push for NSE Project..."

# 1. Reset everything (Delete the old blocked history)
rm -rf .git
echo "✅ Deleted old Git history"

# 2. Re-initialize
git init
git branch -M main
echo "✅ Initialized New Git Repository"

# 3. Connect to GitHub
git remote add origin "$REPO_URL"
echo "✅ Connected to: $REPO_URL"

# 4. Add and Commit
git add .
git commit -m "Fresh Clean Start: Fixed NSE Bot & Scheduling"
echo "✅ Files staged and committed"

# 5. Final Push
# (Remember: Paste your TOKEN as the password)
echo "🚀 One final push to GitHub... (Paste YOUR TOKEN when asked!)"
git push -u origin main --force

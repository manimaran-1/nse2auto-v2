#!/bin/bash

# NSE Market Bot - Service Uninstaller
# This script removes the bot systemd user service.

SERVICE_NAME="nsemarketbot.service"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "----------------------------------------"
echo "🛑 Removing NSE Market Bot Service..."
echo "----------------------------------------"

# 1. Stop the service
systemctl --user stop "$SERVICE_NAME"
echo "✅ Stopped $SERVICE_NAME"

# 2. Disable the service
systemctl --user disable "$SERVICE_NAME"
echo "✅ Disabled $SERVICE_NAME"

# 3. Remove the service file
if [ -f "$USER_SYSTEMD_DIR/$SERVICE_NAME" ]; then
    rm "$USER_SYSTEMD_DIR/$SERVICE_NAME"
    echo "✅ Removed $SERVICE_NAME from $USER_SYSTEMD_DIR"
else
    echo "⚠️  $SERVICE_NAME not found in $USER_SYSTEMD_DIR"
fi

# 4. Reload systemd user daemon
systemctl --user daemon-reload
echo "✅ Systemd user daemon reloaded."

echo "----------------------------------------"
echo "🗑️  Uninstallation Complete!"
echo "----------------------------------------"

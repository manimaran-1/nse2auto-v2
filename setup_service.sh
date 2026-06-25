#!/bin/bash

# NSE Market Bot - Service Installer
# This script sets up the bot to run as a systemd user service.

SERVICE_NAME="nsemarketbot.service"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "----------------------------------------"
echo "🛠️  Setting up NSE Market Bot Service..."
echo "----------------------------------------"

# 1. Create systemd user directory if it doesn't exist
mkdir -p "$USER_SYSTEMD_DIR"

# 2. Copy the service file to the systemd directory
cp "$SERVICE_NAME" "$USER_SYSTEMD_DIR/"
echo "✅ Copied $SERVICE_NAME to $USER_SYSTEMD_DIR"

# 3. Reload systemd user configuration
systemctl --user daemon-reload
echo "✅ Systemd user daemon reloaded."

# 4. Enable and start the service
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"
echo "✅ Service enabled and started."

# 5. Summary
echo "----------------------------------------"
echo "🚀 Setup Complete!"
echo "You can check the status with:"
echo "systemctl --user status $SERVICE_NAME"
echo "----------------------------------------"
echo "Note: If you want this to run after logout, run:"
echo "sudo loginctl enable-linger $USER"
echo "----------------------------------------"

#!/bin/bash

# Setup script for Canadian MP Monitor cache updates

echo "Setting up Canadian MP Monitor cache update cron job..."

# Get the current directory (where the script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_SCRIPT="$SCRIPT_DIR/update_cache.py"
LOG_FILE="$SCRIPT_DIR/cache_update.log"

# Make the update script executable
chmod +x "$UPDATE_SCRIPT"

# Create a cron job entry
CRON_ENTRY="0 */2 * * * cd $SCRIPT_DIR && python3 $UPDATE_SCRIPT >> $LOG_FILE 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "update_cache.py"; then
    echo "Cron job already exists. Updating..."
    # Remove existing entry and add new one
    (crontab -l 2>/dev/null | grep -v "update_cache.py"; echo "$CRON_ENTRY") | crontab -
else
    echo "Adding new cron job..."
    # Add new entry to existing crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

echo "✅ Cron job set up successfully!"
echo "📄 Cache will be updated every 2 hours"
echo "📂 Cache files location: $SCRIPT_DIR/cache/"
echo "📝 Log file location: $LOG_FILE"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To view logs: tail -f $LOG_FILE"
echo "To run update manually: python3 $UPDATE_SCRIPT"

# Run initial update
echo ""
echo "Running initial cache update..."
cd "$SCRIPT_DIR"
python3 "$UPDATE_SCRIPT"
echo ""
echo "🎉 Setup complete!"
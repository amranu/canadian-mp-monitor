#!/bin/bash

# Setup script for Canadian MP Monitor optimized cache updates

echo "Setting up Canadian MP Monitor optimized cache update cron jobs..."

# Get the current directory (where the script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INCREMENTAL_SCRIPT="$SCRIPT_DIR/incremental_update.py"
FULL_CACHE_SCRIPT="$SCRIPT_DIR/cache_all_votes.py"
LOG_FILE="$SCRIPT_DIR/cache_update.log"

# Check if scripts exist
if [ ! -f "$INCREMENTAL_SCRIPT" ]; then
    echo "❌ Error: Incremental update script not found at $INCREMENTAL_SCRIPT"
    exit 1
fi

if [ ! -f "$FULL_CACHE_SCRIPT" ]; then
    echo "❌ Error: Full cache script not found at $FULL_CACHE_SCRIPT"
    exit 1
fi

# Make scripts executable
chmod +x "$INCREMENTAL_SCRIPT"
chmod +x "$FULL_CACHE_SCRIPT"

# Remove old cron jobs first
echo "🧹 Removing old cache update cron jobs..."
crontab -l 2>/dev/null | grep -v "update_cache.py" | crontab -

# Define cron entries
# Incremental updates every 30 minutes (for new votes only)
INCREMENTAL_CRON="*/30 * * * * cd $SCRIPT_DIR && python3 $INCREMENTAL_SCRIPT >> $LOG_FILE 2>&1"

# Full cache rebuild weekly (Sundays at 2 AM) - for maintenance
FULL_CACHE_CRON="0 2 * * 0 cd $SCRIPT_DIR && python3 $FULL_CACHE_SCRIPT >> $LOG_FILE 2>&1"

# Add cron jobs
echo "📝 Adding optimized cache update cron jobs..."
(crontab -l 2>/dev/null; echo "$INCREMENTAL_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$FULL_CACHE_CRON") | crontab -

echo "✅ Cron jobs added successfully!"
echo "⚡ Incremental updates: every 30 minutes (checks for new votes only)"
echo "🔄 Full cache rebuild: weekly on Sundays at 2 AM"
echo "📂 Cache files location: $SCRIPT_DIR/cache/"
echo "📝 Log file location: $LOG_FILE"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "To view logs: tail -f $LOG_FILE"
echo "To run incremental update manually: python3 $INCREMENTAL_SCRIPT"
echo "To run full cache manually: python3 $FULL_CACHE_SCRIPT"

# Run initial incremental update
echo ""
echo "🚀 Running initial incremental update..."
cd "$SCRIPT_DIR"
python3 "$INCREMENTAL_SCRIPT"
echo ""
echo "🎉 Setup complete!"
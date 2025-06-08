#!/bin/bash

# Setup script for Canadian MP Monitor Unified Cache System
# This replaces the complex 4-script system with a single intelligent cache updater

echo "Setting up Canadian MP Monitor unified cache system..."

# Get the current directory (where the script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIFIED_SCRIPT="$SCRIPT_DIR/unified_cache_update.py"
LOG_FILE="$SCRIPT_DIR/cache/unified_cache.log"

# Check if unified script exists
if [ ! -f "$UNIFIED_SCRIPT" ]; then
    echo "❌ Error: Unified cache script not found at $UNIFIED_SCRIPT"
    exit 1
fi

# Make script executable
chmod +x "$UNIFIED_SCRIPT"

echo "🧹 Removing old cache update cron jobs..."
# Remove ALL old cache-related cron jobs
crontab -l 2>/dev/null | grep -v "update_cache.py" | grep -v "incremental_update.py" | grep -v "cache_all_votes.py" | grep -v "fetch_historical_mps.py" | grep -v "cache_mp_voting_records.py" | grep -v "unified_cache_update.py" | crontab -

# Define new unified cron entries
echo "📝 Adding unified cache update cron jobs..."

# Incremental updates every 15 minutes (for new votes and light updates)
INCREMENTAL_CRON="*/15 * * * * cd $SCRIPT_DIR && python3 $UNIFIED_SCRIPT --mode incremental >> $LOG_FILE 2>&1"

# Full auto updates every 4 hours (smart updates based on expiration)
AUTO_CRON="0 */4 * * * cd $SCRIPT_DIR && python3 $UNIFIED_SCRIPT --mode auto >> $LOG_FILE 2>&1"

# Weekly full rebuild on Sundays at 3 AM (complete refresh)
FULL_CRON="0 3 * * 0 cd $SCRIPT_DIR && python3 $UNIFIED_SCRIPT --mode full >> $LOG_FILE 2>&1"

# Add new cron jobs
(crontab -l 2>/dev/null; echo "$INCREMENTAL_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$AUTO_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$FULL_CRON") | crontab -

echo "✅ Unified cache cron jobs added successfully!"
echo ""
echo "📊 New Cache Update Schedule:"
echo "⚡ Incremental updates: every 15 minutes (new votes, light updates)"
echo "🔄 Smart auto updates: every 4 hours (based on cache expiration)"
echo "🔧 Full rebuild: weekly on Sundays at 3 AM (complete refresh)"
echo ""
echo "📂 Cache files location: $SCRIPT_DIR/cache/"
echo "📝 Log file location: $LOG_FILE"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Manual execution commands:"
echo "  • Incremental update: python3 $UNIFIED_SCRIPT --mode incremental"
echo "  • Smart auto update: python3 $UNIFIED_SCRIPT --mode auto"
echo "  • Full rebuild: python3 $UNIFIED_SCRIPT --mode full"
echo "  • Force update: python3 $UNIFIED_SCRIPT --mode auto --force"
echo ""
echo "View logs: tail -f $LOG_FILE"
echo "View statistics: cat $SCRIPT_DIR/cache/unified_cache_statistics.json"
echo ""

# Run initial smart update
echo "🚀 Running initial smart update..."
cd "$SCRIPT_DIR"
python3 "$UNIFIED_SCRIPT" --mode auto --log-level INFO

echo ""
echo "🎉 Unified cache system setup complete!"
echo ""
echo "🔍 Benefits of the new system:"
echo "  • Single intelligent script replaces 4 separate scripts"
echo "  • Smart incremental updates (only fetch new data)"
echo "  • Coordinated API usage prevents rate limiting"
echo "  • Memory-efficient processing for large datasets"
echo "  • Comprehensive statistics and error tracking"
echo "  • Configurable update frequencies per data type"
echo "  • Simplified scheduling (3 cron jobs instead of 4)"
echo ""
echo "📈 Performance improvements:"
echo "  • Reduced API calls through smart caching"
echo "  • Faster updates with incremental processing"
echo "  • Better memory management for vote processing"
echo "  • Coordinated updates prevent duplicate work"
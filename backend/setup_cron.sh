#!/bin/bash

# Setup script for Canadian MP Monitor optimized cache updates

echo "Setting up Canadian MP Monitor optimized cache update cron jobs..."

# Get the current directory (where the script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INCREMENTAL_SCRIPT="$SCRIPT_DIR/incremental_update.py"
FULL_CACHE_SCRIPT="$SCRIPT_DIR/cache_all_votes.py"
HISTORICAL_MPS_SCRIPT="$SCRIPT_DIR/fetch_historical_mps.py"
MP_VOTING_RECORDS_SCRIPT="$SCRIPT_DIR/cache_mp_voting_records.py"
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

if [ ! -f "$HISTORICAL_MPS_SCRIPT" ]; then
    echo "❌ Error: Historical MPs script not found at $HISTORICAL_MPS_SCRIPT"
    exit 1
fi

if [ ! -f "$MP_VOTING_RECORDS_SCRIPT" ]; then
    echo "❌ Error: MP voting records script not found at $MP_VOTING_RECORDS_SCRIPT"
    exit 1
fi

# Make scripts executable
chmod +x "$INCREMENTAL_SCRIPT"
chmod +x "$FULL_CACHE_SCRIPT"
chmod +x "$HISTORICAL_MPS_SCRIPT"
chmod +x "$MP_VOTING_RECORDS_SCRIPT"

# Remove old cron jobs first
echo "🧹 Removing old cache update cron jobs..."
crontab -l 2>/dev/null | grep -v "update_cache.py" | grep -v "incremental_update.py" | grep -v "cache_all_votes.py" | grep -v "fetch_historical_mps.py" | grep -v "cache_mp_voting_records.py" | crontab -

# Define cron entries
# Incremental updates every 30 minutes (for new votes only)
INCREMENTAL_CRON="*/30 * * * * cd $SCRIPT_DIR && python3 $INCREMENTAL_SCRIPT >> $LOG_FILE 2>&1"

# Full cache rebuild weekly (Sundays at 2 AM) - for maintenance
FULL_CACHE_CRON="0 2 * * 0 cd $SCRIPT_DIR && python3 $FULL_CACHE_SCRIPT >> $LOG_FILE 2>&1"

# Historical MPs update monthly (1st of month at 3 AM) - for resolving unknown MPs
HISTORICAL_MPS_CRON="0 3 1 * * cd $SCRIPT_DIR && python3 $HISTORICAL_MPS_SCRIPT >> $LOG_FILE 2>&1"

# MP voting records update daily (daily at 4 AM) - for fast MP detail pages
MP_VOTING_RECORDS_CRON="0 4 * * * cd $SCRIPT_DIR && python3 $MP_VOTING_RECORDS_SCRIPT >> $LOG_FILE 2>&1"

# Add cron jobs
echo "📝 Adding comprehensive cache update cron jobs..."
(crontab -l 2>/dev/null; echo "$INCREMENTAL_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$FULL_CACHE_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$HISTORICAL_MPS_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$MP_VOTING_RECORDS_CRON") | crontab -

echo "✅ Cron jobs added successfully!"
echo "⚡ Incremental updates: every 30 minutes (checks for new votes only)"
echo "🔄 Full cache rebuild: weekly on Sundays at 2 AM"
echo "👥 Historical MPs update: monthly on 1st at 3 AM (resolves unknown MPs)"
echo "📊 MP voting records: daily at 4 AM (fast MP detail pages)"
echo "📂 Cache files location: $SCRIPT_DIR/cache/"
echo "📝 Log file location: $LOG_FILE"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "To view logs: tail -f $LOG_FILE"
echo "Manual execution commands:"
echo "  • Incremental update: python3 $INCREMENTAL_SCRIPT"
echo "  • Full cache rebuild: python3 $FULL_CACHE_SCRIPT"
echo "  • Historical MPs: python3 $HISTORICAL_MPS_SCRIPT"
echo "  • MP voting records: python3 $MP_VOTING_RECORDS_SCRIPT"

# Run initial setup
echo ""
echo "🚀 Running initial setup..."
cd "$SCRIPT_DIR"

# Run incremental update first
echo "Running incremental update..."
python3 "$INCREMENTAL_SCRIPT"

# Run MP voting records update if vote data exists
if [ -d "cache/vote_details" ] && [ "$(ls -A cache/vote_details)" ]; then
    echo "Vote data found, updating MP voting records..."
    python3 "$MP_VOTING_RECORDS_SCRIPT"
else
    echo "No cached vote data found, skipping MP voting records update"
    echo "Run 'python3 cache_all_votes.py' first, then 'python3 cache_mp_voting_records.py'"
fi

echo ""
echo "🎉 Comprehensive cache setup complete!"
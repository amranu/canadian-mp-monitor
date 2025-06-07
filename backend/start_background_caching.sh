#!/bin/bash

# Background caching launcher for session 44-1 missing votes
# This runs inside the Docker container

echo "Starting background caching of missing session 44-1 votes..."
echo "Process will run independently and can be safely interrupted"
echo "Progress will be saved and can be resumed if interrupted"
echo ""

# Run the caching script with nohup so it continues even if connection drops
nohup python3 cache_missing_44_1_votes.py > cache/missing_44_1_output.log 2>&1 &

# Get the process ID
PID=$!
echo "Background caching started with PID: $PID"
echo "Log file: cache/missing_44_1_output.log"
echo "Progress file: cache/missing_44_1_progress.json"
echo ""
echo "To monitor progress:"
echo "  tail -f cache/missing_44_1_output.log"
echo ""
echo "To stop the process:"
echo "  kill $PID"
echo ""
echo "The process will cache approximately 376 votes at ~1 vote per second"
echo "Estimated completion time: 6-10 minutes"
#!/usr/bin/env python3
"""
Background script to cache all missing votes from session 44-1
This runs independently and safely in the background
"""

import requests
import json
import os
import time
import signal
import sys
from datetime import datetime

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Tracker/1.0 (amranu@gmail.com)',
    'API-Version': 'v1'
}

VOTE_DETAILS_CACHE_DIR = 'cache/vote_details'
PROGRESS_FILE = 'cache/missing_44_1_progress.json'
LOG_FILE = 'cache/missing_44_1.log'

# Ensure cache directory exists
os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)
os.makedirs('cache', exist_ok=True)

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n[{datetime.now()}] Shutdown signal received. Finishing current vote and exiting gracefully...")
    shutdown_requested = True

def log(message):
    """Log message to both console and file"""
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_message + '\n')
    except Exception:
        pass  # Don't fail if logging fails

def get_vote_id_from_path(vote_path):
    """Convert vote path to cache-safe ID"""
    return vote_path.replace('/', '_')

def get_cached_vote_details_filename(vote_path):
    """Get filename for cached vote details"""
    vote_id = get_vote_id_from_path(vote_path)
    return os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')

def load_progress():
    """Load progress from previous run"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log(f"Error loading progress: {e}")
    return {'completed': [], 'failed': [], 'last_vote': 0}

def save_progress(progress):
    """Save current progress"""
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        log(f"Error saving progress: {e}")

def find_missing_votes():
    """Find which votes from 1-376 are missing"""
    missing_votes = []
    existing_votes = []
    
    for vote_num in range(1, 377):  # Votes 1-376
        vote_path = f'/votes/44-1/{vote_num}/'
        filename = get_cached_vote_details_filename(vote_path)
        if os.path.exists(filename):
            existing_votes.append(vote_num)
        else:
            missing_votes.append(vote_num)
    
    return missing_votes, existing_votes

def fetch_and_cache_vote(vote_num, progress):
    """Fetch and cache a single vote"""
    try:
        vote_path = f'/votes/44-1/{vote_num}/'
        
        # Get vote details
        vote_response = requests.get(
            f'{PARLIAMENT_API_BASE}{vote_path}',
            headers=HEADERS,
            timeout=15
        )
        
        if vote_response.status_code != 200:
            log(f"  Failed to get vote {vote_num}: HTTP {vote_response.status_code}")
            progress['failed'].append(vote_num)
            return False
        
        vote_data = vote_response.json()
        
        # Small delay between requests
        time.sleep(0.3)
        
        # Get ballots for this vote
        ballots_response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'vote': vote_path,
                'limit': 400  # Get all MPs
            },
            headers=HEADERS,
            timeout=15
        )
        
        if ballots_response.status_code != 200:
            log(f"  Failed to get ballots for vote {vote_num}: HTTP {ballots_response.status_code}")
            progress['failed'].append(vote_num)
            return False
        
        ballots_data = ballots_response.json()
        
        # Create cache data structure
        cache_data = {
            'vote': vote_data,
            'ballots': ballots_data.get('objects', []),
            'cached_at': datetime.now().isoformat(),
            'source': 'missing_44_1_script'
        }
        
        # Save to cache file
        filename = get_cached_vote_details_filename(vote_path)
        with open(filename, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        # Record success
        progress['completed'].append(vote_num)
        progress['last_vote'] = vote_num
        
        vote_desc = vote_data.get('description', {}).get('en', 'Unknown')[:60]
        ballot_count = len(ballots_data.get('objects', []))
        log(f"  ✓ Vote {vote_num}: {vote_desc}... ({ballot_count} ballots)")
        
        return True
        
    except Exception as e:
        log(f"  ✗ Error fetching vote {vote_num}: {e}")
        progress['failed'].append(vote_num)
        return False

def main():
    """Main function"""
    global shutdown_requested
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    log("=== Starting Session 44-1 Missing Votes Caching ===")
    
    # Load previous progress
    progress = load_progress()
    
    # Find missing votes
    missing_votes, existing_votes = find_missing_votes()
    
    log(f"Vote analysis:")
    log(f"  - Already cached: {len(existing_votes)} votes")
    log(f"  - Missing from cache: {len(missing_votes)} votes")
    log(f"  - Previously completed: {len(progress['completed'])} votes")
    log(f"  - Previously failed: {len(progress['failed'])} votes")
    
    # Remove already completed votes from missing list
    remaining_votes = [v for v in missing_votes if v not in progress['completed']]
    
    if not remaining_votes:
        log("All missing votes have been cached! Job complete.")
        return
    
    log(f"Starting to cache {len(remaining_votes)} remaining votes...")
    log(f"Range: {min(remaining_votes)} to {max(remaining_votes)}")
    log(f"This will take approximately {len(remaining_votes) * 0.8 / 60:.1f} minutes")
    
    # Cache remaining votes
    successful = 0
    failed = 0
    start_time = datetime.now()
    
    for i, vote_num in enumerate(remaining_votes, 1):
        if shutdown_requested:
            log("Shutdown requested. Stopping gracefully...")
            break
        
        log(f"[{i}/{len(remaining_votes)}] Fetching vote {vote_num}...")
        
        if fetch_and_cache_vote(vote_num, progress):
            successful += 1
        else:
            failed += 1
        
        # Save progress every 10 votes
        if i % 10 == 0:
            save_progress(progress)
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = i / elapsed * 60 if elapsed > 0 else 0
            remaining_time = (len(remaining_votes) - i) / rate if rate > 0 else 0
            log(f"  Progress: {i}/{len(remaining_votes)} ({i/len(remaining_votes)*100:.1f}%) - {rate:.1f} votes/min - ETA: {remaining_time:.1f} min")
        
        # Rate limiting - be gentle with the API
        time.sleep(0.5)
    
    # Final save
    save_progress(progress)
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log("=== Session 44-1 Missing Votes Caching Complete ===")
    log(f"Successful: {successful}")
    log(f"Failed: {failed}")
    log(f"Total time: {duration/60:.1f} minutes")
    log(f"Rate: {(successful + failed) / duration * 60:.1f} votes/minute")
    
    if progress['failed']:
        log(f"Failed votes that may need retry: {sorted(progress['failed'])}")
    
    # Trigger MP voting records rebuild
    log("Triggering MP voting records rebuild...")
    try:
        import subprocess
        result = subprocess.run(['python3', 'cache_mp_voting_records.py'], 
                              capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            log("MP voting records successfully rebuilt")
        else:
            log(f"MP voting records rebuild failed: {result.stderr}")
    except Exception as e:
        log(f"Error rebuilding MP voting records: {e}")

if __name__ == "__main__":
    main()
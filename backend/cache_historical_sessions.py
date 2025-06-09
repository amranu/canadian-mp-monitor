#!/usr/bin/env python3
"""
Cache Historical MP Votes for Multiple Parliamentary Sessions

This script extends the cache_missing_44_1_votes.py approach to cache
historical MP voting data for key parliamentary sessions that users
interact with in the application.

Target sessions and approximate vote ranges:
- 45-1: Current session (1-50+ votes so far)
- 44-1: Previous session (1-376 votes) - Already handled by existing script
- 43-2: Fall 2019 session (1-250+ votes)
- 43-1: Spring 2019 session (1-300+ votes) 
- 42-1: 2015-2019 parliament (1-800+ votes)
- 41-2: Fall 2013 session (1-200+ votes)
- 41-1: Spring 2011-2013 session (1-400+ votes)

This ensures comprehensive historical coverage for party-line analysis.
"""

import requests
import json
import os
import time
import signal
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Monitor-Historical-Cache/1.0 (contact@mptracker.ca)',
    'API-Version': 'v1'
}

VOTE_DETAILS_CACHE_DIR = 'cache/vote_details'
PROGRESS_FILE = 'cache/historical_sessions_progress.json'
LOG_FILE = 'cache/historical_sessions.log'

# Session configurations with estimated vote ranges
SESSION_CONFIGS = {
    '45-1': {'start': 1, 'end': 100, 'priority': 1},    # Current session - fewer votes so far
    '43-2': {'start': 1, 'end': 300, 'priority': 2},    # Important recent session
    '43-1': {'start': 1, 'end': 350, 'priority': 3},    # Important recent session  
    '42-1': {'start': 1, 'end': 900, 'priority': 4},    # Long parliament - many votes
    '41-2': {'start': 1, 'end': 250, 'priority': 5},    # Fall 2013 session
    '41-1': {'start': 1, 'end': 450, 'priority': 6},    # Spring 2011-2013 session
}

# Global flags
shutdown_requested = False
cache_lock = threading.Lock()

# Ensure cache directory exists
os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)
os.makedirs('cache', exist_ok=True)

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n[{datetime.now()}] Shutdown signal received. Finishing current operations and exiting gracefully...")
    shutdown_requested = True

def log(message, session=None):
    """Thread-safe logging to both console and file"""
    timestamp = datetime.now().isoformat()
    session_prefix = f"[{session}] " if session else ""
    log_message = f"[{timestamp}] {session_prefix}{message}"
    
    print(log_message)
    try:
        with cache_lock:
            with open(LOG_FILE, 'a') as f:
                f.write(log_message + '\n')
    except Exception:
        pass  # Don't fail if logging fails

def get_vote_id_from_path(vote_path):
    """Convert vote path to cache-safe ID: /votes/43-2/156/ -> 43-2_156_"""
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
    
    # Initialize progress structure for all sessions
    progress = {'sessions': {}}
    for session in SESSION_CONFIGS:
        progress['sessions'][session] = {
            'completed': [],
            'failed': [],
            'last_vote': 0,
            'total_votes': 0
        }
    return progress

def save_progress(progress):
    """Thread-safe progress saving"""
    try:
        with cache_lock:
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(progress, f, indent=2)
    except Exception as e:
        log(f"Error saving progress: {e}")

def find_session_vote_range(session):
    """Dynamically discover the actual vote range for a session by checking API"""
    try:
        log(f"Discovering vote range for session {session}...")
        
        # Try to get a high vote number to find the range
        config = SESSION_CONFIGS[session]
        start_check = config['end']
        
        # Binary search to find the actual last vote
        min_vote = 1
        max_vote = start_check
        actual_max = 1
        
        # First, check if our estimated max exists
        test_vote = max_vote
        vote_path = f'/votes/{session}/{test_vote}/'
        
        response = requests.get(f'{PARLIAMENT_API_BASE}{vote_path}', headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            # Our estimate is too low, search higher
            while response.status_code == 200 and test_vote < 2000:
                actual_max = test_vote
                test_vote += 100
                vote_path = f'/votes/{session}/{test_vote}/'
                response = requests.get(f'{PARLIAMENT_API_BASE}{vote_path}', headers=HEADERS, timeout=10)
                time.sleep(0.1)  # Rate limiting
        else:
            # Our estimate is too high, search lower using binary search
            while min_vote <= max_vote:
                mid_vote = (min_vote + max_vote) // 2
                vote_path = f'/votes/{session}/{mid_vote}/'
                response = requests.get(f'{PARLIAMENT_API_BASE}{vote_path}', headers=HEADERS, timeout=10)
                
                if response.status_code == 200:
                    actual_max = mid_vote
                    min_vote = mid_vote + 1
                else:
                    max_vote = mid_vote - 1
                
                time.sleep(0.1)  # Rate limiting
        
        log(f"Session {session}: Found votes 1 to {actual_max}")
        return 1, actual_max
        
    except Exception as e:
        log(f"Error discovering range for session {session}: {e}")
        # Fall back to configured range
        config = SESSION_CONFIGS[session]
        return config['start'], config['end']

def find_missing_votes_for_session(session, start_vote, end_vote):
    """Find which votes are missing from cache for a specific session"""
    missing_votes = []
    existing_votes = []
    
    for vote_num in range(start_vote, end_vote + 1):
        vote_path = f'/votes/{session}/{vote_num}/'
        filename = get_cached_vote_details_filename(vote_path)
        if os.path.exists(filename):
            existing_votes.append(vote_num)
        else:
            missing_votes.append(vote_num)
    
    return missing_votes, existing_votes

def fetch_and_cache_vote(session, vote_num, progress):
    """Fetch and cache a single vote with error handling"""
    try:
        vote_path = f'/votes/{session}/{vote_num}/'
        
        # Get vote details
        vote_response = requests.get(
            f'{PARLIAMENT_API_BASE}{vote_path}',
            headers=HEADERS,
            timeout=15
        )
        
        if vote_response.status_code == 404:
            # Vote doesn't exist - this is normal at the end of ranges
            return 'not_found'
        elif vote_response.status_code != 200:
            log(f"Failed to get vote {session}/{vote_num}: HTTP {vote_response.status_code}", session)
            with cache_lock:
                progress['sessions'][session]['failed'].append(vote_num)
            return 'failed'
        
        vote_data = vote_response.json()
        
        # Small delay between requests
        time.sleep(0.2)
        
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
            log(f"Failed to get ballots for vote {session}/{vote_num}: HTTP {ballots_response.status_code}", session)
            with cache_lock:
                progress['sessions'][session]['failed'].append(vote_num)
            return 'failed'
        
        ballots_data = ballots_response.json()
        
        # Create cache data structure
        cache_data = {
            'vote': vote_data,
            'ballots': ballots_data.get('objects', []),
            'cached_at': datetime.now().isoformat(),
            'source': 'historical_sessions_script',
            'session': session
        }
        
        # Save to cache file
        filename = get_cached_vote_details_filename(vote_path)
        with open(filename, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        # Record success
        with cache_lock:
            progress['sessions'][session]['completed'].append(vote_num)
            progress['sessions'][session]['last_vote'] = vote_num
        
        vote_desc = vote_data.get('description', {}).get('en', 'Unknown')[:50]
        ballot_count = len(ballots_data.get('objects', []))
        log(f"✓ Vote {vote_num}: {vote_desc}... ({ballot_count} ballots)", session)
        
        return 'success'
        
    except Exception as e:
        log(f"✗ Error fetching vote {session}/{vote_num}: {e}", session)
        with cache_lock:
            progress['sessions'][session]['failed'].append(vote_num)
        return 'failed'

def cache_session_votes(session, progress):
    """Cache all missing votes for a specific session"""
    if shutdown_requested:
        return
    
    log(f"=== Starting session {session} ===")
    
    # Discover actual vote range
    start_vote, end_vote = find_session_vote_range(session)
    
    # Find missing votes
    missing_votes, existing_votes = find_missing_votes_for_session(session, start_vote, end_vote)
    
    log(f"Session {session} analysis:", session)
    log(f"  - Vote range: {start_vote} to {end_vote}", session)
    log(f"  - Already cached: {len(existing_votes)} votes", session)
    log(f"  - Missing from cache: {len(missing_votes)} votes", session)
    
    # Remove already completed votes from missing list
    already_completed = progress['sessions'][session]['completed']
    remaining_votes = [v for v in missing_votes if v not in already_completed]
    
    if not remaining_votes:
        log(f"All votes for session {session} are already cached!", session)
        return
    
    log(f"Caching {len(remaining_votes)} remaining votes for session {session}...", session)
    
    # Cache remaining votes
    successful = 0
    failed = 0
    not_found = 0
    start_time = datetime.now()
    
    for i, vote_num in enumerate(remaining_votes, 1):
        if shutdown_requested:
            log(f"Shutdown requested during session {session}. Stopping...", session)
            break
        
        result = fetch_and_cache_vote(session, vote_num, progress)
        
        if result == 'success':
            successful += 1
        elif result == 'failed':
            failed += 1
        elif result == 'not_found':
            not_found += 1
            # Stop trying higher vote numbers if we hit several 404s in a row
            if i > 10 and not_found > 5:
                log(f"Hit multiple 404s, likely reached end of session {session}", session)
                break
        
        # Save progress every 20 votes
        if i % 20 == 0:
            save_progress(progress)
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = i / elapsed * 60 if elapsed > 0 else 0
            log(f"  Progress: {i}/{len(remaining_votes)} ({i/len(remaining_votes)*100:.1f}%) - {rate:.1f} votes/min", session)
        
        # Rate limiting
        time.sleep(0.3)
    
    # Final summary for this session
    elapsed = (datetime.now() - start_time).total_seconds()
    log(f"Session {session} complete: {successful} successful, {failed} failed, {not_found} not found", session)
    log(f"Session {session} took {elapsed/60:.1f} minutes", session)

def main():
    """Main function to cache historical sessions"""
    global shutdown_requested
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    log("=== Starting Historical Sessions Caching ===")
    log(f"Target sessions: {list(SESSION_CONFIGS.keys())}")
    
    # Load previous progress
    progress = load_progress()
    
    # Process sessions in priority order
    sessions_by_priority = sorted(SESSION_CONFIGS.items(), key=lambda x: x[1]['priority'])
    
    overall_start = datetime.now()
    
    for session, config in sessions_by_priority:
        if shutdown_requested:
            break
            
        try:
            cache_session_votes(session, progress)
            save_progress(progress)
        except Exception as e:
            log(f"Error processing session {session}: {e}")
    
    # Final summary
    overall_elapsed = (datetime.now() - overall_start).total_seconds()
    
    log("=== Historical Sessions Caching Complete ===")
    log(f"Total time: {overall_elapsed/60:.1f} minutes")
    
    # Summary by session
    for session in SESSION_CONFIGS:
        session_data = progress['sessions'][session]
        completed = len(session_data['completed'])
        failed = len(session_data['failed'])
        log(f"Session {session}: {completed} completed, {failed} failed")
    
    # Suggest next steps
    log("Consider running party-line statistics update to incorporate new historical data:")
    log("  python3 cache_party_line_stats.py --force")

if __name__ == "__main__":
    main()
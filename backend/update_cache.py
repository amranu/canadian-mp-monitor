#!/usr/bin/env python3
"""
Standalone cache update script for the Canadian MP Monitor
Run this script via cron to keep cache files fresh
"""

import requests
import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Monitor-App/1.0 (contact@example.com)',
    'API-Version': 'v1'
}

CACHE_DURATION = 3600  # 1 hour in seconds
CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def ensure_cache_dirs():
    """Ensure cache directories exist"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)

def save_cache_to_file(data, cache_file):
    """Save cache data to JSON file"""
    try:
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
        log(f"Saved cache to {cache_file}")
        return True
    except Exception as e:
        log(f"Error saving cache to {cache_file}: {e}")
        return False

def load_all_politicians():
    """Load all politicians from the API"""
    log("Loading all politicians from API...")
    all_politicians = []
    offset = 0
    limit = 100
    
    while True:
        try:
            response = requests.get(
                f'{PARLIAMENT_API_BASE}/politicians/',
                params={'limit': limit, 'offset': offset},
                headers=HEADERS,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            all_politicians.extend(data['objects'])
            log(f"Loaded {len(data['objects'])} politicians (total: {len(all_politicians)})")
            
            if not data['pagination']['next_url']:
                break
                
            offset += limit
            
            # Safety break
            if offset > 1000:
                log("Safety break: offset > 1000")
                break
                
        except Exception as e:
            log(f"Error loading politicians at offset {offset}: {e}")
            break
    
    return all_politicians

def load_recent_votes():
    """Load recent votes from the API"""
    log("Loading recent votes from API...")
    try:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/',
            params={'limit': 100, 'offset': 0},
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        votes = response.json()['objects']
        log(f"Loaded {len(votes)} recent votes")
        return votes
    except Exception as e:
        log(f"Error loading votes: {e}")
        return []

def fetch_vote_details(vote_url, ballot):
    """Fetch individual vote details"""
    try:
        vote_response = requests.get(
            f"{PARLIAMENT_API_BASE}{vote_url}",
            headers=HEADERS,
            timeout=10
        )
        vote_response.raise_for_status()
        vote_data = vote_response.json()
        vote_data['mp_ballot'] = ballot
        return vote_data
    except Exception as e:
        log(f"Error fetching vote details for {vote_url}: {e}")
        return None

def get_mp_voting_records(mp_slug, limit=20):
    """Get voting records for a specific MP"""
    try:
        log(f"Loading voting records for {mp_slug}...")
        
        # Get all ballots for this politician
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'politician': f'/politicians/{mp_slug}/',
                'limit': limit,
                'offset': 0
            },
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        ballots_data = response.json()
        
        # For each ballot, get the vote details (batch process)
        votes_with_ballots = []
        vote_urls = [ballot['vote_url'] for ballot in ballots_data['objects']]
        
        # Process votes in smaller batches to avoid overwhelming the API
        batch_size = 5
        for i in range(0, len(vote_urls), batch_size):
            batch_urls = vote_urls[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_ballot = {}
                
                for j, vote_url in enumerate(batch_urls):
                    ballot = ballots_data['objects'][i + j]
                    future = executor.submit(fetch_vote_details, vote_url, ballot['ballot'])
                    future_to_ballot[future] = ballot
                
                for future in as_completed(future_to_ballot):
                    try:
                        vote_data = future.result(timeout=10)
                        if vote_data:
                            votes_with_ballots.append(vote_data)
                    except Exception as e:
                        log(f"Error processing vote: {e}")
                        continue
            
            # Small delay between batches
            time.sleep(0.1)
        
        # Sort by date descending
        votes_with_ballots.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return votes_with_ballots[:limit]
        
    except Exception as e:
        log(f"Error getting MP voting records for {mp_slug}: {e}")
        return []

def update_politicians_cache():
    """Update politicians cache"""
    log("=== Updating Politicians Cache ===")
    politicians = load_all_politicians()
    
    if politicians:
        cache_data = {
            'data': politicians,
            'expires': time.time() + CACHE_DURATION,
            'updated': datetime.now().isoformat(),
            'count': len(politicians)
        }
        
        if save_cache_to_file(cache_data, POLITICIANS_CACHE_FILE):
            log(f"Successfully cached {len(politicians)} politicians")
            return politicians
    
    log("Failed to update politicians cache")
    return []

def update_votes_cache():
    """Update votes cache"""
    log("=== Updating Votes Cache ===")
    votes = load_recent_votes()
    
    if votes:
        cache_data = {
            'data': votes,
            'expires': time.time() + CACHE_DURATION,
            'updated': datetime.now().isoformat(),
            'count': len(votes)
        }
        
        if save_cache_to_file(cache_data, VOTES_CACHE_FILE):
            log(f"Successfully cached {len(votes)} votes")
            return True
    
    log("Failed to update votes cache")
    return False

def update_mp_votes_cache(politicians, max_mps=50):
    """Update MP votes cache for popular MPs"""
    log("=== Updating MP Votes Cache ===")
    
    # Cache votes for first N MPs (most likely to be viewed)
    popular_mps = politicians[:max_mps]
    
    log(f"Caching votes for {len(popular_mps)} MPs")
    successful_updates = 0
    
    for i, mp in enumerate(popular_mps):
        mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
        
        try:
            votes = get_mp_voting_records(mp_slug, 20)
            
            if votes:
                cache_data = {
                    'data': votes,
                    'expires': time.time() + CACHE_DURATION,
                    'updated': datetime.now().isoformat(),
                    'mp_name': mp.get('name', 'Unknown'),
                    'count': len(votes)
                }
                
                mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
                if save_cache_to_file(cache_data, mp_cache_file):
                    successful_updates += 1
                    log(f"Cached {len(votes)} votes for {mp.get('name', mp_slug)} ({i+1}/{len(popular_mps)})")
            
            # Small delay between MPs to avoid overwhelming the API
            time.sleep(0.5)
            
        except Exception as e:
            log(f"Error caching votes for {mp_slug}: {e}")
            continue
    
    log(f"Successfully updated {successful_updates}/{len(popular_mps)} MP vote caches")
    return successful_updates

def main():
    """Main cache update function"""
    start_time = datetime.now()
    log("=== Starting Cache Update Process ===")
    
    ensure_cache_dirs()
    
    # Update politicians cache
    politicians = update_politicians_cache()
    
    # Update votes cache
    update_votes_cache()
    
    # Update MP votes cache if we have politicians data
    if politicians:
        update_mp_votes_cache(politicians, max_mps=50)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log(f"=== Cache Update Complete ===")
    log(f"Total time: {duration:.1f} seconds")

if __name__ == "__main__":
    main()
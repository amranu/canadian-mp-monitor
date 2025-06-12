#!/usr/bin/env python3
"""
Incremental cache update script - only fetches NEW votes and data
This replaces the full cache update for much better performance
"""

import requests
import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Tracker/1.0 (amranu@gmail.com)',
    'API-Version': 'v1'
}

CACHE_DURATION = 10800  # 3 hours in seconds
CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
VOTE_CACHE_INDEX_FILE = os.path.join(CACHE_DIR, 'vote_cache_index.json')

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def ensure_cache_dirs():
    """Ensure cache directories exist"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)

def load_existing_votes():
    """Load existing votes from cache"""
    try:
        if os.path.exists(VOTES_CACHE_FILE):
            with open(VOTES_CACHE_FILE, 'r') as f:
                data = json.load(f)
            return data.get('data', [])
    except Exception as e:
        log(f"Error loading existing votes: {e}")
    return []

def load_vote_cache_index():
    """Load index of cached vote details"""
    try:
        if os.path.exists(VOTE_CACHE_INDEX_FILE):
            with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log(f"Error loading vote cache index: {e}")
    return {'cached_votes': {}, 'last_updated': None}

def save_vote_cache_index(index):
    """Save index of cached vote details"""
    try:
        index['last_updated'] = datetime.now().isoformat()
        with open(VOTE_CACHE_INDEX_FILE, 'w') as f:
            json.dump(index, f, indent=2)
    except Exception as e:
        log(f"Error saving vote cache index: {e}")

def get_vote_id_from_url(vote_url):
    """Extract vote ID from vote URL"""
    return vote_url.replace('/votes/', '').replace('/', '_').strip('_')

def get_vote_details_filename(vote_id):
    """Get filename for vote details cache"""
    safe_vote_id = vote_id.replace('/', '_')
    return os.path.join(VOTE_DETAILS_CACHE_DIR, f'{safe_vote_id}.json')

def fetch_new_votes(existing_votes, limit=50):
    """Fetch only new votes that aren't in our cache"""
    log("Checking for new votes...")
    
    # Get the most recent vote URL from our cache
    latest_cached_url = existing_votes[0]['url'] if existing_votes else None
    
    try:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/',
            params={'limit': limit, 'offset': 0},
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        api_votes = response.json()['objects']
        
        if not latest_cached_url:
            # No cache, return recent votes
            log(f"No cached votes found, returning {len(api_votes)} recent votes")
            return api_votes
        
        # Find new votes (those that come before our latest cached vote)
        new_votes = []
        for vote in api_votes:
            if vote['url'] == latest_cached_url:
                break
            new_votes.append(vote)
        
        log(f"Found {len(new_votes)} new votes since last update")
        return new_votes
        
    except Exception as e:
        log(f"Error fetching new votes: {e}")
        return []

def fetch_vote_details(vote_url, vote_id):
    """Fetch detailed ballot information for a single vote"""
    try:
        # Get the vote details
        vote_response = requests.get(
            f'{PARLIAMENT_API_BASE}{vote_url}',
            headers=HEADERS,
            timeout=20
        )
        vote_response.raise_for_status()
        vote_data = vote_response.json()
        
        # Get all ballots for this vote
        ballots_response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'vote': vote_url,
                'limit': 400  # Get all MPs
            },
            headers=HEADERS,
            timeout=20
        )
        ballots_response.raise_for_status()
        ballots_data = ballots_response.json()
        
        # Combine vote data with ballots
        full_vote_details = {
            'vote': vote_data,
            'ballots': ballots_data.get('objects', []),
            'total_ballots': len(ballots_data.get('objects', [])),
            'cached_at': datetime.now().isoformat()
        }
        
        # Save to individual file
        filename = get_vote_details_filename(vote_id)
        with open(filename, 'w') as f:
            json.dump(full_vote_details, f, indent=2)
        
        log(f"✓ Cached new vote {vote_id} ({len(ballots_data.get('objects', []))} ballots)")
        return vote_id, True
        
    except Exception as e:
        log(f"✗ Error caching vote {vote_id}: {e}")
        return vote_id, False

def cache_new_vote_details(new_votes):
    """Cache detailed information for new votes only"""
    if not new_votes:
        log("No new votes to cache")
        return 0, 0
    
    log(f"Caching details for {len(new_votes)} new votes...")
    
    # Load existing cache index
    cache_index = load_vote_cache_index()
    cached_votes = cache_index.get('cached_votes', {})
    
    successful = 0
    failed = 0
    
    # Process new votes with concurrent requests
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for vote in new_votes:
            vote_id = get_vote_id_from_url(vote['url'])
            future = executor.submit(fetch_vote_details, vote['url'], vote_id)
            futures.append((future, vote['url'], vote_id))
        
        for future, url, vote_id in futures:
            try:
                returned_vote_id, success = future.result(timeout=30)
                if success:
                    successful += 1
                    cached_votes[vote_id] = {
                        'url': url,
                        'cached_at': datetime.now().isoformat()
                    }
                else:
                    failed += 1
            except Exception as e:
                log(f"Future error for vote {vote_id}: {e}")
                failed += 1
    
    # Update cache index
    cache_index['cached_votes'] = cached_votes
    save_vote_cache_index(cache_index)
    
    log(f"New vote details caching complete: {successful} successful, {failed} failed")
    return successful, failed

def update_votes_cache(new_votes, existing_votes):
    """Update the votes cache with new votes"""
    if not new_votes:
        # Refresh cache expiry even if no new votes
        if existing_votes:
            cache_data = {
                'data': existing_votes,
                'expires': time.time() + CACHE_DURATION,
                'updated': datetime.now().isoformat(),
                'count': len(existing_votes)
            }
            with open(VOTES_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            log("Refreshed votes cache expiry")
        return
    
    # Merge new votes with existing ones
    updated_votes = new_votes + existing_votes
    
    cache_data = {
        'data': updated_votes,
        'expires': time.time() + CACHE_DURATION,
        'updated': datetime.now().isoformat(),
        'count': len(updated_votes),
        'new_votes_added': len(new_votes)
    }
    
    try:
        with open(VOTES_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        log(f"Updated votes cache: added {len(new_votes)} new votes (total: {len(updated_votes)})")
    except Exception as e:
        log(f"Error updating votes cache: {e}")

def refresh_politicians_cache():
    """Refresh politicians cache if it's expired"""
    try:
        # Check if cache exists and is still valid
        if os.path.exists(POLITICIANS_CACHE_FILE):
            with open(POLITICIANS_CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            expires = data.get('expires', 0)
            if time.time() < expires:
                log("Politicians cache is still valid, skipping refresh")
                return
        
        log("Refreshing politicians cache...")
        
        # Fetch all politicians
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
                
                if not data['pagination']['next_url']:
                    break
                    
                offset += limit
                
                # Safety break
                if offset > 1000:
                    break
                    
            except Exception as e:
                log(f"Error loading politicians at offset {offset}: {e}")
                break
        
        if all_politicians:
            cache_data = {
                'data': all_politicians,
                'expires': time.time() + CACHE_DURATION,
                'updated': datetime.now().isoformat(),
                'count': len(all_politicians)
            }
            
            with open(POLITICIANS_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            log(f"Refreshed politicians cache with {len(all_politicians)} MPs")
        
    except Exception as e:
        log(f"Error refreshing politicians cache: {e}")

def main():
    """Main incremental update function"""
    start_time = datetime.now()
    log("=== Starting Incremental Cache Update ===")
    
    ensure_cache_dirs()
    
    # Load existing votes
    existing_votes = load_existing_votes()
    log(f"Loaded {len(existing_votes)} existing cached votes")
    
    # Check for new votes
    new_votes = fetch_new_votes(existing_votes)
    
    if new_votes:
        # Cache details for new votes
        successful, failed = cache_new_vote_details(new_votes)
        
        # Update votes cache
        update_votes_cache(new_votes, existing_votes)
        
        log(f"Processed {len(new_votes)} new votes: {successful} cached successfully, {failed} failed")
    else:
        log("No new votes found")
        # Still refresh the votes cache expiry
        update_votes_cache([], existing_votes)
    
    # Refresh politicians cache if needed
    refresh_politicians_cache()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log("=== Incremental Update Complete ===")
    log(f"Total time: {duration:.1f} seconds")
    
    if new_votes:
        log(f"Added {len(new_votes)} new votes to cache")
    else:
        log("No updates needed - cache is current")

if __name__ == "__main__":
    main()
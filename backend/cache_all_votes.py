#!/usr/bin/env python3
"""
Comprehensive vote caching script that pre-fetches and saves all vote details
This eliminates the need to fetch vote details on-demand, dramatically improving performance
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

CACHE_DIR = 'cache'
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
VOTE_CACHE_INDEX_FILE = os.path.join(CACHE_DIR, 'vote_cache_index.json')

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def ensure_cache_dirs():
    """Ensure all cache directories exist"""
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
    # Convert "/votes/45-1/4/" to "45-1/4"
    return vote_url.replace('/votes/', '').replace('/', '_').strip('_')

def get_vote_details_filename(vote_id):
    """Get filename for vote details cache"""
    # Replace any remaining slashes with underscores for safe filename
    safe_vote_id = vote_id.replace('/', '_')
    return os.path.join(VOTE_DETAILS_CACHE_DIR, f'{safe_vote_id}.json')

def fetch_all_votes(limit_per_request=100):
    """Fetch all votes from Parliament API"""
    log("Fetching all votes from Parliament API...")
    all_votes = []
    offset = 0
    
    while True:
        try:
            response = requests.get(
                f'{PARLIAMENT_API_BASE}/votes/',
                params={'limit': limit_per_request, 'offset': offset},
                headers=HEADERS,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            votes = data.get('objects', [])
            if not votes:
                break
                
            all_votes.extend(votes)
            log(f"Fetched {len(votes)} votes (offset: {offset}, total: {len(all_votes)})")
            
            # Check if there are more votes
            if len(votes) < limit_per_request:
                break
                
            offset += limit_per_request
            time.sleep(0.1)  # Be nice to the API
            
        except Exception as e:
            log(f"Error fetching votes at offset {offset}: {e}")
            break
    
    log(f"Total votes fetched: {len(all_votes)}")
    return all_votes

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
        
        log(f"✓ Cached vote {vote_id} ({len(ballots_data.get('objects', []))} ballots)")
        return vote_id, True
        
    except Exception as e:
        log(f"✗ Error caching vote {vote_id}: {e}")
        return vote_id, False

def cache_all_vote_details(votes, max_workers=3):
    """Cache detailed information for all votes"""
    log(f"Starting to cache details for {len(votes)} votes...")
    
    # Load existing cache index
    cache_index = load_vote_cache_index()
    cached_votes = cache_index.get('cached_votes', {})
    
    # Filter out votes that are already cached
    votes_to_cache = []
    for vote in votes:
        vote_id = get_vote_id_from_url(vote['url'])
        filename = get_vote_details_filename(vote_id)
        
        if not os.path.exists(filename):
            votes_to_cache.append((vote['url'], vote_id))
        else:
            # Mark as already cached in index
            cached_votes[vote_id] = {
                'url': vote['url'],
                'cached_at': datetime.fromtimestamp(os.path.getmtime(filename)).isoformat()
            }
    
    log(f"Need to cache {len(votes_to_cache)} new votes ({len(votes) - len(votes_to_cache)} already cached)")
    
    if not votes_to_cache:
        log("All votes already cached!")
        return
    
    successful = 0
    failed = 0
    
    # Process in batches with concurrent requests
    batch_size = 20
    for i in range(0, len(votes_to_cache), batch_size):
        batch = votes_to_cache[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(votes_to_cache) + batch_size - 1) // batch_size
        
        log(f"Processing batch {batch_num}/{total_batches} ({len(batch)} votes)...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_vote = {
                executor.submit(fetch_vote_details, url, vote_id): (url, vote_id) 
                for url, vote_id in batch
            }
            
            for future in as_completed(future_to_vote):
                url, vote_id = future_to_vote[future]
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
        
        # Save progress after each batch
        cache_index['cached_votes'] = cached_votes
        save_vote_cache_index(cache_index)
        log(f"Batch {batch_num} complete. Progress: {successful} successful, {failed} failed")
        
        # Small delay between batches
        if i + batch_size < len(votes_to_cache):
            time.sleep(1)
    
    log(f"Vote details caching complete: {successful} successful, {failed} failed")
    return successful, failed

def calculate_party_statistics(ballots):
    """Calculate party voting statistics from ballots"""
    party_stats = {}
    
    for ballot in ballots:
        # We'll need to enrich this data with MP details later
        # For now, just count the ballots
        party = ballot.get('mp_party', 'Unknown')
        if party not in party_stats:
            party_stats[party] = {
                'total': 0,
                'yes': 0,
                'no': 0,
                'paired': 0,
                'absent': 0,
                'other': 0
            }
        
        party_stats[party]['total'] += 1
        vote = ballot['ballot'].lower()
        if vote == 'yes':
            party_stats[party]['yes'] += 1
        elif vote == 'no':
            party_stats[party]['no'] += 1
        elif vote == 'paired':
            party_stats[party]['paired'] += 1
        elif vote == 'absent':
            party_stats[party]['absent'] += 1
        else:
            party_stats[party]['other'] += 1
    
    return party_stats

def main():
    """Main function to cache all vote details"""
    start_time = datetime.now()
    log("=== Starting Comprehensive Vote Caching ===")
    
    ensure_cache_dirs()
    
    # Fetch all votes
    all_votes = fetch_all_votes()
    if not all_votes:
        log("No votes found, exiting")
        return
    
    # Cache detailed information for all votes
    successful, failed = cache_all_vote_details(all_votes)
    
    # Update vote cache index with summary
    cache_index = load_vote_cache_index()
    cache_index.update({
        'total_votes': len(all_votes),
        'cached_count': successful,
        'failed_count': failed,
        'completion_time': datetime.now().isoformat()
    })
    save_vote_cache_index(cache_index)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log("=== Comprehensive Vote Caching Complete ===")
    log(f"Total votes: {len(all_votes)}")
    log(f"Successfully cached: {successful}")
    log(f"Failed: {failed}")
    log(f"Total time: {duration:.1f} seconds")
    log(f"Average time per vote: {duration/max(successful, 1):.2f} seconds")

if __name__ == "__main__":
    main()
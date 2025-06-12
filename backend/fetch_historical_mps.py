#!/usr/bin/env python3
"""
Script to fetch and cache historical MP data for previous parliamentary sessions
This resolves "Unknown" MPs in vote details from previous parliaments
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
    'User-Agent': 'MP-Tracker/1.0 (amranu@gmail.com)',
    'API-Version': 'v1'
}

CACHE_DIR = 'cache'
HISTORICAL_MPS_FILE = os.path.join(CACHE_DIR, 'historical_mps.json')

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def ensure_cache_dir():
    """Ensure cache directory exists"""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_sample_previous_session_votes():
    """Get a sample of votes from previous session to find MP URLs"""
    log("Getting sample votes from previous parliamentary session...")
    
    try:
        # Get votes from session 44-1 (previous parliament)
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/',
            params={
                'limit': 50,
                'session': '44-1'  # Previous parliamentary session
            },
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        votes_data = response.json()
        
        log(f"Found {len(votes_data['objects'])} votes from session 44-1")
        return votes_data['objects']
        
    except Exception as e:
        log(f"Error getting sample votes: {e}")
        return []

def get_mp_urls_from_votes(votes):
    """Extract unique MP URLs from vote ballots"""
    log("Extracting MP URLs from vote ballots...")
    
    mp_urls = set()
    
    for i, vote in enumerate(votes[:10]):  # Check first 10 votes
        try:
            vote_path = vote['url'].replace('/votes/', '').replace('/', '')
            log(f"Checking vote {i+1}/{min(10, len(votes))}: {vote_path}")
            
            # Get ballots for this vote
            response = requests.get(
                f'{PARLIAMENT_API_BASE}/votes/ballots/',
                params={
                    'vote': vote['url'],
                    'limit': 400  # Get all MPs
                },
                headers=HEADERS,
                timeout=30
            )
            response.raise_for_status()
            ballots_data = response.json()
            
            # Extract MP URLs
            for ballot in ballots_data['objects']:
                if ballot.get('politician_url'):
                    mp_urls.add(ballot['politician_url'])
            
            log(f"Found {len(ballots_data['objects'])} ballots, total unique MPs so far: {len(mp_urls)}")
            
            # Small delay to be nice to the API
            time.sleep(0.2)
            
        except Exception as e:
            log(f"Error processing vote {vote.get('url', 'unknown')}: {e}")
            continue
    
    log(f"Found {len(mp_urls)} unique MP URLs from previous session")
    return list(mp_urls)

def fetch_mp_details(mp_url):
    """Fetch details for a single MP"""
    try:
        mp_slug = mp_url.replace('/politicians/', '').replace('/', '')
        
        response = requests.get(
            f'{PARLIAMENT_API_BASE}{mp_url}',
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        mp_data = response.json()
        
        log(f"✓ Fetched details for {mp_data.get('name', mp_slug)}")
        return mp_url, mp_data
        
    except Exception as e:
        log(f"✗ Error fetching {mp_url}: {e}")
        return mp_url, None

def fetch_all_historical_mps(mp_urls):
    """Fetch details for all historical MPs using concurrent requests"""
    log(f"Fetching details for {len(mp_urls)} historical MPs...")
    
    historical_mps = {}
    successful = 0
    failed = 0
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all requests
        future_to_url = {executor.submit(fetch_mp_details, url): url for url in mp_urls}
        
        # Process completed requests
        for future in as_completed(future_to_url):
            mp_url = future_to_url[future]
            try:
                url, mp_data = future.result()
                if mp_data:
                    historical_mps[url] = mp_data
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                log(f"Error processing future for {mp_url}: {e}")
                failed += 1
            
            # Progress update every 10 MPs
            if (successful + failed) % 10 == 0:
                log(f"Progress: {successful} successful, {failed} failed, {len(mp_urls) - successful - failed} remaining")
    
    log(f"Completed: {successful} successful, {failed} failed")
    return historical_mps

def save_historical_mps(historical_mps):
    """Save historical MP data to cache file"""
    try:
        cache_data = {
            'data': historical_mps,
            'updated': datetime.now().isoformat(),
            'count': len(historical_mps),
            'description': 'Historical MP data for previous parliamentary sessions'
        }
        
        with open(HISTORICAL_MPS_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        log(f"Saved {len(historical_mps)} historical MPs to {HISTORICAL_MPS_FILE}")
        return True
        
    except Exception as e:
        log(f"Error saving historical MPs: {e}")
        return False

def load_existing_historical_mps():
    """Load existing historical MP data if available"""
    try:
        if os.path.exists(HISTORICAL_MPS_FILE):
            with open(HISTORICAL_MPS_FILE, 'r') as f:
                data = json.load(f)
            log(f"Loaded {len(data.get('data', {}))} existing historical MPs")
            return data.get('data', {})
    except Exception as e:
        log(f"Error loading existing data: {e}")
    
    return {}

def main():
    """Main function to fetch and cache historical MP data"""
    start_time = datetime.now()
    log("=== Starting Historical MP Data Fetch ===")
    
    ensure_cache_dir()
    
    # Load existing data
    existing_mps = load_existing_historical_mps()
    
    # Get sample votes from previous session
    votes = get_sample_previous_session_votes()
    if not votes:
        log("No votes found, exiting")
        return
    
    # Extract MP URLs
    mp_urls = get_mp_urls_from_votes(votes)
    if not mp_urls:
        log("No MP URLs found, exiting")
        return
    
    # Filter out MPs we already have
    new_mp_urls = [url for url in mp_urls if url not in existing_mps]
    log(f"Need to fetch {len(new_mp_urls)} new MPs (already have {len(existing_mps)})")
    
    if new_mp_urls:
        # Fetch new MP details
        new_historical_mps = fetch_all_historical_mps(new_mp_urls)
        
        # Merge with existing data
        all_historical_mps = {**existing_mps, **new_historical_mps}
    else:
        all_historical_mps = existing_mps
        log("No new MPs to fetch")
    
    # Save to cache
    if save_historical_mps(all_historical_mps):
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        log("=== Historical MP Data Fetch Complete ===")
        log(f"Total MPs in cache: {len(all_historical_mps)}")
        log(f"Total time: {duration:.1f} seconds")
        
        # Show sample of data
        log("\\nSample MPs cached:")
        for i, (url, mp_data) in enumerate(list(all_historical_mps.items())[:5]):
            name = mp_data.get('name', 'Unknown')
            party = mp_data.get('memberships', [{}])[-1].get('party', {}).get('short_name', {}).get('en', 'Unknown')
            log(f"  {i+1}. {name} ({party})")
    else:
        log("Failed to save historical MP data")

if __name__ == "__main__":
    main()
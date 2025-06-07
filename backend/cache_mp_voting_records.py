#!/usr/bin/env python3
"""
Cache MP voting records using existing cached vote data
This creates comprehensive voting records for each MP without additional API calls
"""

import json
import os
import time
from datetime import datetime
from collections import defaultdict

# Configuration
CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')
HISTORICAL_MPS_FILE = os.path.join(CACHE_DIR, 'historical_mps.json')

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def load_politicians():
    """Load all politicians from cache"""
    try:
        if os.path.exists(POLITICIANS_CACHE_FILE):
            with open(POLITICIANS_CACHE_FILE, 'r') as f:
                data = json.load(f)
            return data.get('data', [])
    except Exception as e:
        log(f"Error loading politicians: {e}")
    return []

def load_historical_mps():
    """Load historical MPs from cache"""
    try:
        if os.path.exists(HISTORICAL_MPS_FILE):
            with open(HISTORICAL_MPS_FILE, 'r') as f:
                data = json.load(f)
            return data.get('data', {})
    except Exception as e:
        log(f"Error loading historical MPs: {e}")
    return {}

def get_cached_vote_files():
    """Get list of cached vote files without loading them into memory"""
    vote_files = []
    if not os.path.exists(VOTE_DETAILS_CACHE_DIR):
        return vote_files
    
    for filename in sorted(os.listdir(VOTE_DETAILS_CACHE_DIR)):
        if filename.endswith('.json'):
            filepath = os.path.join(VOTE_DETAILS_CACHE_DIR, filename)
            vote_files.append(filepath)
    
    return vote_files

def extract_mp_slug_from_url(url):
    """Extract MP slug from politician URL"""
    return url.replace('/politicians/', '').replace('/', '')

def build_and_save_mp_voting_records(vote_files, politicians, historical_mps):
    """Build and save MP voting records incrementally to manage memory efficiently"""
    log(f"Building MP voting records from {len(vote_files)} cached vote files...")
    
    # Create MP lookup maps
    current_mp_map = {mp['url']: mp for mp in politicians}
    all_mp_map = {**current_mp_map, **historical_mps}
    
    # Initialize MP record files
    os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)
    mp_record_files = {}
    
    # Process votes in small batches to manage memory
    batch_size = 50  # Smaller batches for better memory management
    processed = 0
    
    for i in range(0, len(vote_files), batch_size):
        batch_files = vote_files[i:i + batch_size]
        
        # Temporary storage for this batch only
        batch_mp_records = defaultdict(list)
        
        # Process this batch of vote files
        for vote_file in batch_files:
            try:
                with open(vote_file, 'r') as f:
                    vote_data = json.load(f)
                
                if 'ballots' not in vote_data or 'vote' not in vote_data:
                    continue
                    
                vote_info = vote_data['vote']
                ballots = vote_data['ballots']
                
                # Create vote record template
                vote_record = {
                    'url': vote_info.get('url', ''),
                    'date': vote_info.get('date', ''),
                    'number': vote_info.get('number', ''),
                    'session': vote_info.get('session', ''),
                    'result': vote_info.get('result', ''),
                    'description': vote_info.get('description', {}),
                    'bill_url': vote_info.get('bill_url'),
                    'yea_total': vote_info.get('yea_total', 0),
                    'nay_total': vote_info.get('nay_total', 0),
                    'paired_total': vote_info.get('paired_total', 0)
                }
                
                # Add each MP's ballot to their voting record
                for ballot in ballots:
                    mp_url = ballot.get('politician_url')
                    if mp_url and mp_url in all_mp_map:
                        mp_slug = extract_mp_slug_from_url(mp_url)
                        
                        # Create MP-specific vote record
                        mp_vote_record = {
                            **vote_record,
                            'mp_ballot': ballot.get('ballot', 'Unknown')
                        }
                        
                        batch_mp_records[mp_slug].append(mp_vote_record)
                
                processed += 1
                
            except Exception as e:
                log(f"Error processing vote file {vote_file}: {e}")
                continue
        
        # Append batch records to existing MP files
        append_mp_records_to_files(batch_mp_records, mp_record_files)
        
        # Clear batch memory
        del batch_mp_records
        
        # Log progress after each batch
        log(f"Processed {processed}/{len(vote_files)} vote files...")
    
    # Finalize all MP record files (sort and save)
    finalize_mp_record_files(mp_record_files)
    
    log(f"Built voting records for {len(mp_record_files)} MPs")
    return len(mp_record_files)

def append_mp_records_to_files(batch_mp_records, mp_record_files):
    """Append batch MP records to temporary files"""
    for mp_slug, votes in batch_mp_records.items():
        if mp_slug not in mp_record_files:
            # Create temporary file for this MP
            temp_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.temp.json')
            mp_record_files[mp_slug] = temp_file
            
            # Initialize with empty list
            with open(temp_file, 'w') as f:
                json.dump([], f)
        
        # Append votes to existing temp file
        temp_file = mp_record_files[mp_slug]
        try:
            # Load existing votes
            with open(temp_file, 'r') as f:
                existing_votes = json.load(f)
            
            # Append new votes
            existing_votes.extend(votes)
            
            # Save back
            with open(temp_file, 'w') as f:
                json.dump(existing_votes, f)
                
        except Exception as e:
            log(f"Error appending records for {mp_slug}: {e}")

def finalize_mp_record_files(mp_record_files):
    """Sort and save final MP record files"""
    log("Finalizing MP voting records...")
    
    successful = 0
    failed = 0
    total_mps = len(mp_record_files)
    
    for i, (mp_slug, temp_file) in enumerate(mp_record_files.items(), 1):
        try:
            # Load all votes for this MP
            with open(temp_file, 'r') as f:
                all_votes = json.load(f)
            
            # Sort by date (most recent first)
            all_votes.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            # Create final cache data
            cache_data = {
                'data': all_votes,
                'expires': time.time() + 10800,  # 3 hours
                'updated': datetime.now().isoformat(),
                'count': len(all_votes),
                'source': 'cached_vote_analysis'
            }
            
            # Save to final file
            final_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
            with open(final_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            # Remove temp file
            os.remove(temp_file)
            
            successful += 1
            
            # Progress updates
            if successful % 10 == 0 or i == total_mps:
                log(f"Finalized voting records for {successful}/{total_mps} MPs...")
                
        except Exception as e:
            log(f"Error finalizing voting record for {mp_slug}: {e}")
            failed += 1
            
            # Clean up temp file on error
            try:
                os.remove(temp_file)
            except:
                pass
    
    log(f"MP voting records finalized: {successful} successful, {failed} failed")
    return successful, failed

def save_mp_voting_records(mp_voting_records):
    """Save MP voting records to individual cache files"""
    log("Saving MP voting records to cache files...")
    
    os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)
    
    successful = 0
    failed = 0
    
    total_mps = len(mp_voting_records)
    for i, (mp_slug, votes) in enumerate(mp_voting_records.items(), 1):
        try:
            cache_data = {
                'data': votes,
                'expires': time.time() + 10800,  # 3 hours
                'updated': datetime.now().isoformat(),
                'count': len(votes),
                'source': 'cached_vote_analysis'
            }
            
            mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
            with open(mp_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            successful += 1
            
            # More frequent progress updates
            if successful % 10 == 0 or i == total_mps:
                log(f"Saved voting records for {successful}/{total_mps} MPs...")
                
        except Exception as e:
            log(f"Error saving voting record for {mp_slug}: {e}")
            failed += 1
    
    log(f"MP voting records saved: {successful} successful, {failed} failed")
    return successful, failed

def generate_statistics(mp_voting_records, politicians, historical_mps):
    """Generate statistics about the cached voting records"""
    log("Generating statistics...")
    
    total_mps = len(mp_voting_records)
    total_votes = sum(len(votes) for votes in mp_voting_records.values())
    
    # Count MPs by type
    current_mp_count = 0
    historical_mp_count = 0
    
    current_mp_urls = {mp['url'] for mp in politicians}
    
    for mp_slug in mp_voting_records:
        mp_url = f'/politicians/{mp_slug}/'
        if mp_url in current_mp_urls:
            current_mp_count += 1
        else:
            historical_mp_count += 1
    
    # Vote count statistics
    vote_counts = [len(votes) for votes in mp_voting_records.values()]
    avg_votes = sum(vote_counts) / len(vote_counts) if vote_counts else 0
    max_votes = max(vote_counts) if vote_counts else 0
    min_votes = min(vote_counts) if vote_counts else 0
    
    stats = {
        'total_mps_with_records': total_mps,
        'current_mps': current_mp_count,
        'historical_mps': historical_mp_count,
        'total_vote_records': total_votes,
        'average_votes_per_mp': round(avg_votes, 1),
        'max_votes_per_mp': max_votes,
        'min_votes_per_mp': min_votes,
        'generated_at': datetime.now().isoformat()
    }
    
    # Save statistics
    stats_file = os.path.join(CACHE_DIR, 'mp_voting_statistics.json')
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Display statistics
    log("=== MP Voting Records Statistics ===")
    log(f"Total MPs with voting records: {total_mps}")
    log(f"  - Current MPs: {current_mp_count}")
    log(f"  - Historical MPs: {historical_mp_count}")
    log(f"Total vote records: {total_votes:,}")
    log(f"Average votes per MP: {avg_votes:.1f}")
    log(f"Vote range: {min_votes} - {max_votes} votes per MP")
    
    return stats

def main():
    """Main function to cache MP voting records"""
    start_time = datetime.now()
    log("=== Starting MP Voting Records Caching ===")
    
    # Load all required data
    log("Loading cached data...")
    politicians = load_politicians()
    historical_mps = load_historical_mps()
    vote_files = get_cached_vote_files()
    
    log(f"Loaded {len(politicians)} current politicians")
    log(f"Loaded {len(historical_mps)} historical MPs") 
    log(f"Found {len(vote_files)} cached vote files")
    
    if not vote_files:
        log("No cached vote files found. Run cache_all_votes.py first.")
        return
    
    # Build and save MP voting records incrementally
    total_mps = build_and_save_mp_voting_records(vote_files, politicians, historical_mps)
    
    if not total_mps:
        log("No voting records could be built from cached data.")
        return
    
    # Generate simple completion statistics
    log("=== MP Voting Records Statistics ===")
    log(f"Total MPs with voting records: {total_mps}")
    log(f"Current politicians loaded: {len(politicians)}")
    log(f"Historical MPs loaded: {len(historical_mps)}")
    
    # Save basic statistics
    stats = {
        'total_mps_with_records': total_mps,
        'current_mps': len(politicians),
        'historical_mps': len(historical_mps),
        'generated_at': datetime.now().isoformat(),
        'processing_method': 'incremental_memory_efficient'
    }
    
    stats_file = os.path.join(CACHE_DIR, 'mp_voting_statistics.json')
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log("=== MP Voting Records Caching Complete ===")
    log(f"Total time: {duration:.1f} seconds")
    log(f"Average time per MP: {duration/max(total_mps, 1):.2f} seconds")

if __name__ == "__main__":
    main()
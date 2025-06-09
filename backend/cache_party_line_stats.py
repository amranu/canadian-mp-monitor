#!/usr/bin/env python3
"""
Party-Line Voting Statistics Calculator and Cache

This script analyzes voting records to calculate accurate party-line voting statistics
by examining actual party majority positions rather than using heuristics.

Features:
- Calculates party-line voting percentages for all MPs
- Determines actual party positions from ballot data
- Tracks party discipline and cohesion statistics
- Caches results for fast API serving
- Supports session-based filtering and analysis
"""

import json
import os
import time
import gc
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import glob
import argparse

# Cache configuration
CACHE_DIR = 'cache'
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')
PARTY_LINE_CACHE_FILE = os.path.join(CACHE_DIR, 'party_line_stats.json')
PARTY_LINE_CACHE_DURATION = 7200  # 2 hours in seconds
MAX_MEMORY_MB = 1000  # Maximum memory usage in MB before forcing cleanup


def get_memory_usage_mb():
    """Get current memory usage in MB (basic version without psutil)"""
    try:
        # Read from /proc/self/status on Linux
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    # Extract memory in kB and convert to MB
                    return int(line.split()[1]) / 1024
    except:
        pass
    
    # Fallback: return 0 if we can't determine memory usage
    return 0


def check_memory_and_cleanup(max_memory_mb=None):
    """Check memory usage and force cleanup if needed"""
    if max_memory_mb is None:
        max_memory_mb = MAX_MEMORY_MB
    current_memory = get_memory_usage_mb()
    if current_memory > max_memory_mb:
        print(f"Memory usage ({current_memory:.1f}MB) exceeds limit ({max_memory_mb}MB), forcing cleanup...")
        gc.collect()
        return True
    return False


def get_party_variations(party):
    """Get party name variations for matching"""
    variations = {
        'Conservative': ['Conservative', 'CPC', 'Conservative Party', 'Tory'],
        'Liberal': ['Liberal', 'Liberal Party', 'Lib'],
        'NDP': ['NDP', 'New Democratic Party', 'New Democrat'],
        'Bloc': ['Bloc', 'Bloc Québécois', 'BQ'],
        'Green': ['Green', 'Green Party'],
        'Independent': ['Independent', 'Ind.', 'Non-affiliated']
    }
    return variations.get(party, [party])


def extract_party_from_ballot(ballot, politicians_lookup=None):
    """Extract party name from ballot object with multiple fallbacks"""
    party_name = ''
    
    # Try various party field names in the ballot data structure
    if ballot.get('mp_party'):
        party_name = ballot['mp_party']
    elif ballot.get('politician_party'):
        party_name = ballot['politician_party']
    elif ballot.get('party'):
        party_name = ballot['party']
    elif ballot.get('politician', {}).get('current_party', {}).get('short_name', {}).get('en'):
        party_name = ballot['politician']['current_party']['short_name']['en']
    elif ballot.get('politician', {}).get('party'):
        party_name = ballot['politician']['party']
    else:
        # If no party info in ballot, try to look up from politician_url
        politician_url = ballot.get('politician_url', '')
        if politician_url and politicians_lookup:
            # Extract slug from URL like '/politicians/ziad-aboultaif/'
            slug = politician_url.replace('/politicians/', '').replace('/', '')
            party_name = politicians_lookup.get(slug, '')
    
    return party_name.strip()


def normalize_party_name(party):
    """Normalize party names to standard format"""
    party_lower = party.lower()
    
    if 'conservative' in party_lower or 'cpc' in party_lower:
        return 'Conservative'
    elif 'liberal' in party_lower and 'new' not in party_lower:
        return 'Liberal'
    elif 'ndp' in party_lower or 'new democratic' in party_lower:
        return 'NDP'
    elif 'bloc' in party_lower:
        return 'Bloc'
    elif 'green' in party_lower:
        return 'Green'
    elif 'independent' in party_lower:
        return 'Independent'
    else:
        return party  # Keep original if no match


def calculate_party_position(ballots, party, politicians_lookup=None):
    """
    Calculate party majority position for a specific vote
    Returns party voting statistics and majority position
    """
    normalized_party = normalize_party_name(party)
    
    party_ballots = []
    for ballot in ballots:
        ballot_party = extract_party_from_ballot(ballot, politicians_lookup)
        if ballot_party:
            normalized_ballot_party = normalize_party_name(ballot_party)
            if normalized_ballot_party == normalized_party:
                party_ballots.append(ballot)

    if not party_ballots:
        return {
            'total': 0,
            'yes': 0,
            'no': 0,
            'paired': 0,
            'absent': 0,
            'majority_position': None,
            'cohesion': 0
        }

    vote_counts = {
        'yes': sum(1 for b in party_ballots if b.get('ballot') == 'Yes'),
        'no': sum(1 for b in party_ballots if b.get('ballot') == 'No'),
        'paired': sum(1 for b in party_ballots if b.get('ballot') == 'Paired'),
        'absent': sum(1 for b in party_ballots if not b.get('ballot') or b.get('ballot') == 'Absent')
    }

    substantive_votes = vote_counts['yes'] + vote_counts['no']
    majority_position = 'Yes' if vote_counts['yes'] > vote_counts['no'] else 'No'
    majority_count = max(vote_counts['yes'], vote_counts['no'])
    
    # Calculate party cohesion (how unified the party was)
    cohesion = (majority_count / substantive_votes * 100) if substantive_votes > 0 else 0

    return {
        'total': len(party_ballots),
        'yes': vote_counts['yes'],
        'no': vote_counts['no'],
        'paired': vote_counts['paired'],
        'absent': vote_counts['absent'],
        'majority_position': majority_position if substantive_votes > 0 else None,
        'cohesion': round(cohesion, 1)
    }


def did_vote_with_party(mp_vote, party_majority_position):
    """Check if MP voted with their party majority"""
    if not party_majority_position or not mp_vote:
        return False
    if mp_vote not in ['Yes', 'No']:
        return False  # Skip paired/absent votes
    
    return mp_vote == party_majority_position


def load_vote_details(vote_id):
    """Load vote details from cache"""
    vote_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
    try:
        if os.path.exists(vote_file):
            with open(vote_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading vote details for {vote_id}: {e}")
    return None


def get_all_cached_votes():
    """Get all available cached vote details"""
    vote_files = glob.glob(os.path.join(VOTE_DETAILS_CACHE_DIR, '*.json'))
    votes_data = {}
    
    for vote_file in vote_files:
        vote_id = os.path.basename(vote_file).replace('.json', '')
        vote_data = load_vote_details(vote_id)
        if vote_data and 'ballots' in vote_data:
            votes_data[vote_id] = vote_data
    
    print(f"Loaded {len(votes_data)} cached votes")
    return votes_data


def calculate_mp_party_line_stats(mp_slug, mp_party, votes_data, politicians_lookup=None):
    """Calculate comprehensive party-line statistics for an MP"""
    party_line_votes = 0
    total_eligible_votes = 0
    party_discipline_breaks = []
    party_loyalty_by_session = defaultdict(lambda: {'party_line': 0, 'total': 0})
    
    # Process each vote to calculate party-line adherence
    for vote_id, vote_data in votes_data.items():
        try:
            ballots = vote_data.get('ballots', [])
            if not ballots:
                continue
            
            vote_info = vote_data.get('vote', {})
            
            # Find this MP's ballot in the vote
            mp_ballot = None
            for ballot in ballots:
                # Check politician_url field (main field in vote data)
                politician_url = ballot.get('politician_url', '')
                if f'/politicians/{mp_slug}/' in politician_url:
                    mp_ballot = ballot.get('ballot')
                    break
                
                # Fallback: check other possible name fields
                mp_name_fields = [
                    ballot.get('mp_name', ''),
                    ballot.get('politician_name', ''),
                    ballot.get('politician', {}).get('name', ''),
                    ballot.get('name', '')
                ]
                
                mp_slug_fields = [
                    ballot.get('mp_slug', ''),
                    ballot.get('politician_slug', ''),
                    ballot.get('politician', {}).get('slug', ''),
                    ballot.get('slug', '')
                ]
                
                # Match by slug or name (fallback)
                if (mp_slug in mp_slug_fields or 
                    any(mp_slug.replace('-', ' ').lower() in name.lower() for name in mp_name_fields if name)):
                    mp_ballot = ballot.get('ballot')
                    break
            
            if not mp_ballot or mp_ballot not in ['Yes', 'No']:
                continue  # Skip if MP didn't vote or vote wasn't Yes/No
            
            # Calculate party position for this vote
            party_stats = calculate_party_position(ballots, mp_party, politicians_lookup)
            
            if not party_stats['majority_position']:
                continue  # Skip if party didn't have clear majority position
            
            total_eligible_votes += 1
            voted_with_party = did_vote_with_party(mp_ballot, party_stats['majority_position'])
            
            if voted_with_party:
                party_line_votes += 1
            else:
                # Record party discipline break
                party_discipline_breaks.append({
                    'vote_id': vote_id,
                    'mp_vote': mp_ballot,
                    'party_position': party_stats['majority_position'],
                    'date': vote_info.get('date'),
                    'description': vote_info.get('description', {}).get('en', 'Parliamentary Vote')
                })
            
            # Track session-based stats
            session = vote_info.get('session', 'unknown')
            party_loyalty_by_session[session]['total'] += 1
            if voted_with_party:
                party_loyalty_by_session[session]['party_line'] += 1
            
            
        except Exception as e:
            print(f"Error processing vote {vote_id} for {mp_slug}: {e}")
            continue
    
    # Calculate final statistics
    party_line_percentage = (party_line_votes / total_eligible_votes * 100) if total_eligible_votes > 0 else 0
    
    # Calculate session percentages
    session_stats = {}
    for session, stats in party_loyalty_by_session.items():
        percentage = (stats['party_line'] / stats['total'] * 100) if stats['total'] > 0 else 0
        session_stats[session] = {
            'party_line': stats['party_line'],
            'total': stats['total'],
            'percentage': round(percentage, 1)
        }
    
    return {
        'mp_slug': mp_slug,
        'mp_party': mp_party,
        'party_line_votes': party_line_votes,
        'total_eligible_votes': total_eligible_votes,
        'party_line_percentage': round(party_line_percentage, 1),
        'party_discipline_breaks': party_discipline_breaks[:10],  # Limit to 10 most recent
        'party_loyalty_by_session': session_stats,
        'methodology': 'actual_party_majority',
        'calculated_at': datetime.now().isoformat()
    }


def get_all_mps_from_votes(votes_data):
    """Extract all MP slugs and parties from vote data"""
    mps = {}  # {mp_slug: mp_party}
    
    for vote_data in votes_data.values():
        ballots = vote_data.get('ballots', [])
        for ballot in ballots:
            # Extract MP slug and party
            mp_slug_fields = [
                ballot.get('mp_slug', ''),
                ballot.get('politician_slug', ''),
                ballot.get('politician', {}).get('slug', ''),
                ballot.get('slug', '')
            ]
            
            mp_slug = next((slug for slug in mp_slug_fields if slug), None)
            mp_party = extract_party_from_ballot(ballot)
            
            if mp_slug and mp_party:
                mps[mp_slug] = normalize_party_name(mp_party)
    
    print(f"Found {len(mps)} unique MPs in vote data")
    return mps


def get_mp_list_from_cache():
    """Get list of MPs from politicians cache instead of loading all vote data"""
    try:
        politicians_file = os.path.join(CACHE_DIR, 'politicians.json')
        if os.path.exists(politicians_file):
            with open(politicians_file, 'r') as f:
                data = json.load(f)
            
            mps = {}
            # Try both 'objects' and 'data' fields (different cache formats)
            mp_list = data.get('objects', []) or data.get('data', [])
            for mp in mp_list:
                if mp.get('url'):
                    slug = mp['url'].replace('/politicians/', '').replace('/', '')
                    party = mp.get('current_party', {}).get('short_name', {}).get('en', 'Unknown')
                    if party:
                        mps[slug] = party
            
            print(f"Found {len(mps)} MPs from politicians cache")
            return mps
    except Exception as e:
        print(f"Error loading MPs from politicians cache: {e}")
    
    return {}

def get_votes_for_mp_analysis(mp_slug, max_votes=5000):
    """Get votes for MP analysis, prioritizing by session (45-1, 44-1, 43-2, etc.)"""
    vote_files = glob.glob(os.path.join(VOTE_DETAILS_CACHE_DIR, '*.json'))
    votes_data = {}
    
    # Define session priority order (most recent first)
    session_priority = ['45-1', '44-1', '43-2', '43-1', '42-1', '41-2', '41-1', '40-3', '40-2', '40-1', '39-2', '39-1']
    
    # Group vote files by session
    votes_by_session = {}
    for vote_file in vote_files:
        vote_id = os.path.basename(vote_file).replace('.json', '')
        
        # Extract session from vote_id, handling both formats:
        # New format: "44-1_451_" -> "44-1"
        # Old format: "_votes_44-1_1_" -> "44-1"
        session = None
        if vote_id.startswith('_votes_'):
            # Old format: _votes_44-1_1_ -> extract 44-1
            parts = vote_id.split('_')
            if len(parts) >= 3:
                session = parts[2]  # _votes_44-1_1_ -> parts[2] = "44-1"
        elif '_' in vote_id:
            # New format: 44-1_451_ -> extract 44-1
            session = vote_id.split('_')[0]
        
        if session and session in session_priority:
            if session not in votes_by_session:
                votes_by_session[session] = []
            votes_by_session[session].append(vote_file)
    
    processed_votes = 0
    mp_politician_url = f'/politicians/{mp_slug}/'
    
    # Process sessions in priority order
    for session in session_priority:
        if session not in votes_by_session:
            continue
            
        print(f"  Checking session {session} for {mp_slug}...")
        session_vote_count = 0
        
        # Sort files in this session by modification time (most recent first)
        session_files = votes_by_session[session]
        session_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        for vote_file in session_files:
            if processed_votes >= max_votes:
                break
                
            vote_id = os.path.basename(vote_file).replace('.json', '')
            vote_data = load_vote_details(vote_id)
            
            if vote_data and 'ballots' in vote_data:
                # Check if this MP is in this vote
                mp_found = False
                for ballot in vote_data['ballots']:
                    politician_url = ballot.get('politician_url', '')
                    if politician_url == mp_politician_url:
                        mp_found = True
                        break
                    
                    # Fallback: check other possible fields
                    if (mp_slug in str(ballot.get('mp_slug', '')) or 
                        mp_slug.replace('-', ' ').lower() in str(ballot.get('mp_name', '')).lower()):
                        mp_found = True
                        break
                
                if mp_found:
                    votes_data[vote_id] = vote_data
                    processed_votes += 1
                    session_vote_count += 1
        
        if session_vote_count > 0:
            print(f"  Found {session_vote_count} votes in session {session} for {mp_slug}")
    
    return votes_data

def load_existing_party_line_cache():
    """Load existing party-line cache to resume processing"""
    try:
        if os.path.exists(PARTY_LINE_CACHE_FILE):
            with open(PARTY_LINE_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading existing cache: {e}")
    return None

def save_incremental_results(mp_slug, mp_stats, existing_data=None):
    """Save results incrementally for one MP"""
    if existing_data is None:
        existing_data = {
            'summary': {
                'total_mps_analyzed': 0,
                'total_votes_analyzed': 0,
                'avg_party_line_percentage': 0,
                'calculation_date': datetime.now().isoformat(),
                'cache_expires': (datetime.now() + timedelta(seconds=PARTY_LINE_CACHE_DURATION)).isoformat()
            },
            'mp_stats': {}
        }
    
    # Add/update MP stats
    existing_data['mp_stats'][mp_slug] = mp_stats
    
    # Update summary
    all_stats = existing_data['mp_stats']
    existing_data['summary']['total_mps_analyzed'] = len(all_stats)
    existing_data['summary']['avg_party_line_percentage'] = round(
        sum(stats['party_line_percentage'] for stats in all_stats.values()) / len(all_stats), 1
    ) if all_stats else 0
    existing_data['summary']['calculation_date'] = datetime.now().isoformat()
    
    # Save to file
    save_party_line_cache(existing_data)
    return existing_data

def calculate_all_party_line_stats(memory_limit_mb=MAX_MEMORY_MB, max_votes_per_mp=5000, force_recalculate=False):
    """Calculate party-line statistics for all MPs with memory-efficient processing"""
    print(f"[{datetime.now()}] Starting memory-efficient party-line statistics calculation...")
    
    # Track sessions found across all MPs
    all_sessions = set()
    
    # Get MPs from politicians cache (much more memory efficient)
    all_mps = get_mp_list_from_cache()
    if not all_mps:
        print("No MP data available")
        return None
    
    # Load existing cache to resume if needed (unless force flag is set)
    existing_data = None
    already_processed = set()
    
    if not force_recalculate:
        existing_data = load_existing_party_line_cache()
        if existing_data and 'mp_stats' in existing_data:
            already_processed = set(existing_data['mp_stats'].keys())
            print(f"Found existing cache with {len(already_processed)} MPs already processed")
    else:
        print("Force recalculation enabled - starting fresh")
    
    # Process MPs one at a time to minimize memory usage
    processed = len(already_processed)
    
    for mp_slug, mp_party in all_mps.items():
        if mp_slug in already_processed:
            continue  # Skip already processed MPs
            
        try:
            print(f"Processing MP {processed + 1}/{len(all_mps)}: {mp_slug}")
            
            # Get limited vote data for this MP only
            mp_votes_data = get_votes_for_mp_analysis(mp_slug, max_votes=max_votes_per_mp)
            
            if not mp_votes_data:
                print(f"No vote data found for {mp_slug}, skipping...")
                continue
            else:
                print(f"Found {len(mp_votes_data)} votes for {mp_slug}")
            
            # Calculate stats for this MP
            stats = calculate_mp_party_line_stats(mp_slug, mp_party, mp_votes_data, all_mps)
            
            # Collect sessions from this MP
            for session in stats.get('party_loyalty_by_session', {}).keys():
                all_sessions.add(session)
            
            # Save results incrementally
            existing_data = save_incremental_results(mp_slug, stats, existing_data)
            
            # Clear memory and check usage
            del mp_votes_data
            gc.collect()
            
            processed += 1
            
            # Check memory usage and log progress
            current_memory = get_memory_usage_mb()
            if processed % 10 == 0:
                print(f"Processed {processed}/{len(all_mps)} MPs... Memory: {current_memory:.1f}MB")
            
            # Force cleanup if memory usage is too high
            if check_memory_and_cleanup(memory_limit_mb):
                print(f"Memory cleanup performed after processing {mp_slug}")
                
        except Exception as e:
            print(f"Error calculating stats for {mp_slug}: {e}")
            continue
    
    # Final summary update with session statistics
    if existing_data:
        existing_data['summary']['cache_expires'] = (datetime.now() + timedelta(seconds=PARTY_LINE_CACHE_DURATION)).isoformat()
        existing_data['summary']['sessions_analyzed'] = sorted(list(all_sessions), reverse=True)
        
        # Calculate session-based summary statistics
        session_summary = calculate_session_summary_stats(existing_data['mp_stats'])
        existing_data['session_summary'] = session_summary
        
        save_party_line_cache(existing_data)
    
    print(f"[{datetime.now()}] Completed party-line calculation for {processed} MPs across {len(all_sessions)} sessions")
    return existing_data


def calculate_session_summary_stats(mp_stats):
    """Calculate summary statistics by parliamentary session"""
    session_stats = {}
    
    # Collect all sessions and their data
    for mp_slug, stats in mp_stats.items():
        mp_party = stats.get('mp_party', 'Unknown')
        
        for session, session_data in stats.get('party_loyalty_by_session', {}).items():
            if session not in session_stats:
                session_stats[session] = {
                    'total_mps': 0,
                    'total_votes_analyzed': 0,
                    'avg_party_line_percentage': 0,
                    'party_breakdown': {},
                    'mp_count_by_party': {}
                }
            
            session_stats[session]['total_mps'] += 1
            session_stats[session]['total_votes_analyzed'] += session_data.get('total', 0)
            
            # Track by party
            if mp_party not in session_stats[session]['party_breakdown']:
                session_stats[session]['party_breakdown'][mp_party] = {
                    'mp_count': 0,
                    'avg_party_line_percentage': 0,
                    'total_party_line_votes': 0,
                    'total_eligible_votes': 0
                }
            
            party_stats = session_stats[session]['party_breakdown'][mp_party]
            party_stats['mp_count'] += 1
            party_stats['total_party_line_votes'] += session_data.get('party_line', 0)
            party_stats['total_eligible_votes'] += session_data.get('total', 0)
            
            # Count MPs by party for session
            session_stats[session]['mp_count_by_party'][mp_party] = party_stats['mp_count']
    
    # Calculate averages and percentages
    for session, stats in session_stats.items():
        total_party_line_votes = 0
        total_eligible_votes = 0
        
        for party, party_data in stats['party_breakdown'].items():
            if party_data['total_eligible_votes'] > 0:
                party_data['avg_party_line_percentage'] = round(
                    (party_data['total_party_line_votes'] / party_data['total_eligible_votes']) * 100, 1
                )
            
            total_party_line_votes += party_data['total_party_line_votes']
            total_eligible_votes += party_data['total_eligible_votes']
        
        # Overall session average
        if total_eligible_votes > 0:
            stats['avg_party_line_percentage'] = round(
                (total_party_line_votes / total_eligible_votes) * 100, 1
            )
    
    return session_stats


def save_party_line_cache(data):
    """Save party-line statistics to cache file"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(PARTY_LINE_CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now()}] Saved party-line cache to {PARTY_LINE_CACHE_FILE}")
        return True
    except Exception as e:
        print(f"Error saving party-line cache: {e}")
        return False


def load_party_line_cache():
    """Load party-line statistics from cache file"""
    try:
        if os.path.exists(PARTY_LINE_CACHE_FILE):
            with open(PARTY_LINE_CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            # Check if cache is still valid
            cache_expires = datetime.fromisoformat(data['summary']['cache_expires'])
            if datetime.now() < cache_expires:
                print(f"[{datetime.now()}] Loaded valid party-line cache")
                return data
            else:
                print(f"[{datetime.now()}] Party-line cache expired")
        
    except Exception as e:
        print(f"Error loading party-line cache: {e}")
    
    return None


def main():
    """Main function to calculate and cache party-line statistics"""
    parser = argparse.ArgumentParser(description='Calculate party-line voting statistics')
    parser.add_argument('--force', action='store_true', help='Force recalculation even if cache exists')
    parser.add_argument('--memory-limit', type=int, default=MAX_MEMORY_MB, help='Memory limit in MB')
    parser.add_argument('--max-votes', type=int, default=5000, help='Maximum votes to analyze per MP')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of MPs to process before reporting')
    
    args = parser.parse_args()
    
    print(f"[{datetime.now()}] Party-line statistics caching started")
    print(f"Memory limit: {args.memory_limit}MB, Max votes per MP: {args.max_votes}")
    
    # Try to load existing cache first
    if not args.force:
        cached_data = load_party_line_cache()
        if cached_data:
            print("Valid cache found, skipping recalculation (use --force to override)")
            return
    
    # Calculate new statistics
    stats_data = calculate_all_party_line_stats(args.memory_limit, args.max_votes, args.force)
    if stats_data:
        if save_party_line_cache(stats_data):
            print(f"[{datetime.now()}] Party-line statistics cache updated successfully")
            print(f"Processed {stats_data['summary']['total_mps_analyzed']} MPs")
        else:
            print(f"[{datetime.now()}] Failed to save party-line statistics cache")
    else:
        print(f"[{datetime.now()}] Failed to calculate party-line statistics")


def update_party_line_after_vote_cache():
    """Function to be called after vote cache updates to refresh party-line stats"""
    print(f"[{datetime.now()}] Checking if party-line cache needs update after vote cache refresh...")
    
    # Check if party-line cache is expired
    cached_data = load_party_line_cache()
    if not cached_data:
        print("Party-line cache not found, triggering calculation...")
        calculate_all_party_line_stats()
    else:
        # Check age of cache
        try:
            cache_expires = datetime.fromisoformat(cached_data['summary']['cache_expires'])
            if datetime.now() >= cache_expires:
                print("Party-line cache expired, triggering recalculation...")
                calculate_all_party_line_stats()
            else:
                print("Party-line cache is still valid")
        except:
            print("Error checking cache expiration, triggering recalculation...")
            calculate_all_party_line_stats()


if __name__ == '__main__':
    main()
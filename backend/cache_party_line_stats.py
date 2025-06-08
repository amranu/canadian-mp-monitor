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
from datetime import datetime, timedelta
from collections import defaultdict
import glob

# Cache configuration
CACHE_DIR = 'cache'
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')
PARTY_LINE_CACHE_FILE = os.path.join(CACHE_DIR, 'party_line_stats.json')
PARTY_LINE_CACHE_DURATION = 7200  # 2 hours in seconds


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


def extract_party_from_ballot(ballot):
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


def calculate_party_position(ballots, party):
    """
    Calculate party majority position for a specific vote
    Returns party voting statistics and majority position
    """
    normalized_party = normalize_party_name(party)
    
    party_ballots = []
    for ballot in ballots:
        ballot_party = extract_party_from_ballot(ballot)
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


def calculate_mp_party_line_stats(mp_slug, mp_party, votes_data):
    """Calculate comprehensive party-line statistics for an MP"""
    party_line_votes = 0
    total_eligible_votes = 0
    party_discipline_breaks = []
    party_loyalty_by_session = defaultdict(lambda: {'party_line': 0, 'total': 0})
    cohesion_stats = []
    
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
                # Check various name fields to match the MP
                mp_name_fields = [
                    ballot.get('mp_name', ''),
                    ballot.get('politician_name', ''),
                    ballot.get('politician', {}).get('name', ''),
                    ballot.get('name', '')
                ]
                
                # Also check slug matching
                mp_slug_fields = [
                    ballot.get('mp_slug', ''),
                    ballot.get('politician_slug', ''),
                    ballot.get('politician', {}).get('slug', ''),
                    ballot.get('slug', '')
                ]
                
                # Match by slug (most reliable) or name
                if (mp_slug in mp_slug_fields or 
                    any(mp_slug.replace('-', ' ').lower() in name.lower() for name in mp_name_fields if name)):
                    mp_ballot = ballot.get('ballot')
                    break
            
            if not mp_ballot or mp_ballot not in ['Yes', 'No']:
                continue  # Skip if MP didn't vote or vote wasn't Yes/No
            
            # Calculate party position for this vote
            party_stats = calculate_party_position(ballots, mp_party)
            
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
                    'party_cohesion': party_stats['cohesion'],
                    'date': vote_info.get('date'),
                    'description': vote_info.get('description', {}).get('en', 'Parliamentary Vote')
                })
            
            # Track session-based stats
            session = vote_info.get('session', 'unknown')
            party_loyalty_by_session[session]['total'] += 1
            if voted_with_party:
                party_loyalty_by_session[session]['party_line'] += 1
            
            # Track cohesion stats
            cohesion_stats.append({
                'vote_id': vote_id,
                'cohesion': party_stats['cohesion'],
                'voted_with_party': voted_with_party
            })
            
        except Exception as e:
            print(f"Error processing vote {vote_id} for {mp_slug}: {e}")
            continue
    
    # Calculate final statistics
    party_line_percentage = (party_line_votes / total_eligible_votes * 100) if total_eligible_votes > 0 else 0
    avg_party_cohesion = (sum(stat['cohesion'] for stat in cohesion_stats) / len(cohesion_stats)) if cohesion_stats else 0
    
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
        'avg_party_cohesion': round(avg_party_cohesion, 1),
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


def calculate_all_party_line_stats():
    """Calculate party-line statistics for all MPs"""
    print(f"[{datetime.now()}] Starting party-line statistics calculation...")
    
    # Load all cached vote data
    votes_data = get_all_cached_votes()
    if not votes_data:
        print("No cached vote data available")
        return None
    
    # Get all MPs from vote data
    all_mps = get_all_mps_from_votes(votes_data)
    
    # Calculate stats for each MP
    all_stats = {}
    processed = 0
    
    for mp_slug, mp_party in all_mps.items():
        try:
            stats = calculate_mp_party_line_stats(mp_slug, mp_party, votes_data)
            all_stats[mp_slug] = stats
            processed += 1
            
            if processed % 50 == 0:
                print(f"Processed {processed}/{len(all_mps)} MPs...")
                
        except Exception as e:
            print(f"Error calculating stats for {mp_slug}: {e}")
            continue
    
    # Add summary statistics
    summary = {
        'total_mps_analyzed': len(all_stats),
        'total_votes_analyzed': len(votes_data),
        'avg_party_line_percentage': round(
            sum(stats['party_line_percentage'] for stats in all_stats.values()) / len(all_stats), 1
        ) if all_stats else 0,
        'calculation_date': datetime.now().isoformat(),
        'cache_expires': (datetime.now() + timedelta(seconds=PARTY_LINE_CACHE_DURATION)).isoformat()
    }
    
    result = {
        'summary': summary,
        'mp_stats': all_stats
    }
    
    print(f"[{datetime.now()}] Completed party-line calculation for {len(all_stats)} MPs")
    return result


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
    print(f"[{datetime.now()}] Party-line statistics caching started")
    
    # Try to load existing cache first
    cached_data = load_party_line_cache()
    if cached_data:
        print("Valid cache found, skipping recalculation")
        return
    
    # Calculate new statistics
    stats_data = calculate_all_party_line_stats()
    if stats_data:
        if save_party_line_cache(stats_data):
            print(f"[{datetime.now()}] Party-line statistics cache updated successfully")
        else:
            print(f"[{datetime.now()}] Failed to save party-line statistics cache")
    else:
        print(f"[{datetime.now()}] Failed to calculate party-line statistics")


if __name__ == '__main__':
    main()
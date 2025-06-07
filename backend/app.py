from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import threading
import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Monitor-App/1.0 (contact@example.com)',
    'API-Version': 'v1'
}

# Cache configuration
CACHE_DURATION = 10800  # 3 hours in seconds
CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')
HISTORICAL_MPS_FILE = os.path.join(CACHE_DIR, 'historical_mps.json')
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
VOTE_CACHE_INDEX_FILE = os.path.join(CACHE_DIR, 'vote_cache_index.json')
BILLS_CACHE_FILE = os.path.join(CACHE_DIR, 'bills.json')

# Ensure cache directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)
os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)

# In-memory cache for fast access (loaded from files)
cache = {
    'politicians': {'data': None, 'expires': 0, 'loading': False},
    'votes': {'data': None, 'expires': 0, 'loading': False},
    'bills': {'data': None, 'expires': 0, 'loading': False},
    'mp_votes': {},  # {mp_slug: {'data': [...], 'expires': timestamp, 'loading': False}}
    'mp_details': {},  # Cache for individual MP details fetched from API
    'historical_mps': {'data': {}, 'loaded': False}  # Historical MP data from previous sessions
}

@app.route('/')
def hello():
    politicians_status = 'cached' if is_cache_valid('politicians') else 'expired/empty'
    votes_status = 'cached' if is_cache_valid('votes') else 'expired/empty'
    bills_status = 'cached' if is_cache_valid('bills') else 'expired/empty'
    
    politicians_count = len(cache['politicians']['data']) if cache['politicians']['data'] else 0
    votes_count = len(cache['votes']['data']) if cache['votes']['data'] else 0
    bills_count = len(cache['bills']['data']) if cache['bills']['data'] else 0
    mp_votes_count = len([k for k, v in cache['mp_votes'].items() if v.get('data')])
    mp_votes_loading = len([k for k, v in cache['mp_votes'].items() if v.get('loading', False)])
    historical_mps_count = len(cache['historical_mps']['data'])
    
    politicians_expires = datetime.fromtimestamp(cache['politicians']['expires']).isoformat() if cache['politicians']['expires'] > 0 else 'N/A'
    votes_expires = datetime.fromtimestamp(cache['votes']['expires']).isoformat() if cache['votes']['expires'] > 0 else 'N/A'
    bills_expires = datetime.fromtimestamp(cache['bills']['expires']).isoformat() if cache['bills']['expires'] > 0 else 'N/A'
    
    return jsonify({
        'message': 'Canadian MP Monitor Backend',
        'cache_status': {
            'politicians': {
                'status': politicians_status,
                'count': politicians_count,
                'expires': politicians_expires
            },
            'votes': {
                'status': votes_status,
                'count': votes_count,
                'expires': votes_expires
            },
            'bills': {
                'status': bills_status,
                'count': bills_count,
                'expires': bills_expires
            },
            'mp_votes': {
                'cached_mps': mp_votes_count,
                'loading_mps': mp_votes_loading,
                'total_cached_records': sum(len(v.get('data', [])) for v in cache['mp_votes'].values() if v.get('data'))
            },
            'historical_mps': {
                'loaded': cache['historical_mps']['loaded'],
                'count': historical_mps_count
            }
        },
        'cache_duration_hours': CACHE_DURATION / 3600
    })

def load_cache_from_file(cache_file):
    """Load cache data from JSON file"""
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading cache from {cache_file}: {e}")
    return None

def save_cache_to_file(data, cache_file):
    """Save cache data to JSON file"""
    try:
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        print(f"[{datetime.now()}] Saved cache to {cache_file}")
    except Exception as e:
        print(f"Error saving cache to {cache_file}: {e}")

def is_cache_valid(cache_key):
    return cache[cache_key]['data'] is not None and time.time() < cache[cache_key]['expires']

def get_vote_id_from_path(vote_path):
    """Convert vote path to cache-safe ID"""
    return vote_path.replace('/', '_')

def get_cached_vote_details_filename(vote_path):
    """Get filename for cached vote details"""
    vote_id = get_vote_id_from_path(vote_path)
    return os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')

def load_cached_vote_details(vote_path):
    """Load vote details from cache file"""
    try:
        # Handle both URL formats: 44-1/451 -> 44-1_451
        if '/' in vote_path:
            vote_path = vote_path.replace('/', '_')
            
        filename = get_cached_vote_details_filename(vote_path)
        print(f"[{datetime.now()}] Looking for vote cache file: {filename}")
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
            print(f"[{datetime.now()}] Loaded cached vote details for {vote_path}")
            return data
        else:
            print(f"[{datetime.now()}] Vote cache file not found: {filename}")
    except Exception as e:
        print(f"[{datetime.now()}] Error loading cached vote details for {vote_path}: {e}")
    return None

def enrich_cached_vote_details(cached_data):
    """Enrich cached vote details with current MP data and party statistics"""
    if not cached_data or 'ballots' not in cached_data:
        return cached_data
    
    # For large historical votes, skip enrichment to avoid timeouts
    ballot_count = len(cached_data['ballots'])
    if ballot_count > 500:  # Increased limit since we have cached MP data
        print(f"[{datetime.now()}] Skipping enrichment for very large vote with {ballot_count} ballots to avoid timeout")
        return cached_data
    
    # Get politician maps
    politicians = cache['politicians'].get('data', [])
    politician_map = {mp['url']: mp for mp in politicians} if politicians else {}
    historical_mps = cache['historical_mps'].get('data', {})
    
    # Enrich ballots with MP details
    enriched_ballots = []
    historical_mp_count = 0
    current_mp_count = 0
    api_fetched_count = 0
    
    for ballot in cached_data['ballots']:
        mp_data = politician_map.get(ballot['politician_url'], {})
        
        # Check historical MPs if not found in current
        if not mp_data and ballot['politician_url'] in historical_mps:
            mp_data = historical_mps[ballot['politician_url']]
            historical_mp_count += 1
        elif mp_data:
            current_mp_count += 1
        else:
            # Skip API fetching for historical votes to avoid timeouts
            print(f"[{datetime.now()}] Skipping API fetch for {ballot['politician_url']} to avoid timeout")
            api_fetched_count += 1
        
        # Extract party and riding info
        if mp_data and mp_data.get('memberships'):
            latest_membership = mp_data['memberships'][-1]
            party_name = latest_membership.get('party', {}).get('short_name', {}).get('en', 'Unknown')
            riding_name = latest_membership.get('riding', {}).get('name', {}).get('en', 'Unknown')
            province = latest_membership.get('riding', {}).get('province', 'Unknown')
        else:
            party_name = mp_data.get('current_party', {}).get('short_name', {}).get('en', 'Unknown')
            riding_name = mp_data.get('current_riding', {}).get('name', {}).get('en', 'Unknown')
            province = mp_data.get('current_riding', {}).get('province', 'Unknown')
        
        enriched_ballot = {
            **ballot,
            'mp_name': mp_data.get('name', 'Unknown'),
            'mp_party': party_name,
            'mp_riding': riding_name,
            'mp_province': province,
            'mp_image': mp_data.get('image', None)
        }
        enriched_ballots.append(enriched_ballot)
    
    # Calculate party statistics
    party_stats = {}
    for ballot in enriched_ballots:
        party = ballot['mp_party']
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
    
    # Return enriched data
    return {
        'vote': cached_data.get('vote', {}),
        'ballots': enriched_ballots,
        'party_stats': party_stats,
        'total_ballots': len(enriched_ballots),
        'mp_sources': {
            'current_mps': current_mp_count,
            'historical_mps': historical_mp_count,
            'api_fetched': api_fetched_count,
            'total': len(enriched_ballots)
        },
        'from_cache': True
    }

def load_historical_mps():
    """Load historical MP data from cache file"""
    try:
        if os.path.exists(HISTORICAL_MPS_FILE):
            with open(HISTORICAL_MPS_FILE, 'r') as f:
                historical_data = json.load(f)
            cache['historical_mps']['data'] = historical_data.get('data', {})
            cache['historical_mps']['loaded'] = True
            print(f"[{datetime.now()}] Loaded {len(cache['historical_mps']['data'])} historical MPs")
        else:
            print(f"[{datetime.now()}] No historical MPs file found, will fetch unknown MPs from API")
    except Exception as e:
        print(f"[{datetime.now()}] Error loading historical MPs: {e}")
        cache['historical_mps']['data'] = {}
        cache['historical_mps']['loaded'] = True

def load_persistent_cache():
    """Load all cache data from files on startup"""
    print(f"[{datetime.now()}] Loading persistent cache from files...")
    
    # Load politicians
    politicians_data = load_cache_from_file(POLITICIANS_CACHE_FILE)
    if politicians_data:
        cache['politicians'] = {
            'data': politicians_data.get('data', []),
            'expires': politicians_data.get('expires', 0),
            'loading': False
        }
        print(f"[{datetime.now()}] Loaded {len(cache['politicians']['data'])} politicians from cache")
    
    # Load votes
    votes_data = load_cache_from_file(VOTES_CACHE_FILE)
    if votes_data:
        cache['votes'] = {
            'data': votes_data.get('data', []),
            'expires': votes_data.get('expires', 0),
            'loading': False
        }
        print(f"[{datetime.now()}] Loaded {len(cache['votes']['data'])} votes from cache")
    
    # Load bills
    bills_data = load_cache_from_file(BILLS_CACHE_FILE)
    if bills_data:
        cache['bills'] = {
            'data': bills_data.get('data', []),
            'expires': bills_data.get('expires', 0),
            'loading': False
        }
        print(f"[{datetime.now()}] Loaded {len(cache['bills']['data'])} bills from cache")
    
    # Only count MP votes cache files, don't load them into memory at startup
    mp_cache_count = 0
    if os.path.exists(MP_VOTES_CACHE_DIR):
        mp_cache_count = len([f for f in os.listdir(MP_VOTES_CACHE_DIR) if f.endswith('.json')])
        print(f"[{datetime.now()}] Found {mp_cache_count} MP vote cache files (loading on-demand)")
    
    # Load historical MPs
    load_historical_mps()

def load_mp_votes_on_demand(mp_slug):
    """Load MP voting records from cache file on-demand"""
    try:
        mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
        if os.path.exists(mp_cache_file):
            mp_data = load_cache_from_file(mp_cache_file)
            if mp_data:
                # Handle both old format (list) and new format (dict with data/expires)
                if isinstance(mp_data, list):
                    cache['mp_votes'][mp_slug] = {
                        'data': mp_data,
                        'expires': time.time() + CACHE_DURATION,
                        'loading': False
                    }
                else:
                    cache['mp_votes'][mp_slug] = {
                        'data': mp_data.get('data', []),
                        'expires': mp_data.get('expires', 0),
                        'loading': False
                    }
                print(f"[{datetime.now()}] Loaded {len(cache['mp_votes'][mp_slug]['data'])} votes for {mp_slug} on-demand")
                return True
    except Exception as e:
        print(f"[{datetime.now()}] Error loading MP votes for {mp_slug}: {e}")
    return False

# Load cache on startup
load_persistent_cache()

def load_all_politicians():
    """Load all politicians from the API"""
    all_politicians = []
    offset = 0
    limit = 100
    
    while True:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/politicians/',
            params={'limit': limit, 'offset': offset},
            headers=HEADERS
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
    
    return all_politicians

def update_politicians_cache():
    """Update the politicians cache"""
    try:
        if cache['politicians']['loading']:
            return False
            
        cache['politicians']['loading'] = True
        print(f"[{datetime.now()}] Loading politicians from API...")
        
        all_politicians = load_all_politicians()
        
        cache['politicians']['data'] = all_politicians
        cache['politicians']['expires'] = time.time() + CACHE_DURATION
        cache['politicians']['loading'] = False
        
        # Save to file
        save_cache_to_file({
            'data': all_politicians,
            'expires': cache['politicians']['expires'],
            'updated': datetime.now().isoformat()
        }, POLITICIANS_CACHE_FILE)
        
        print(f"[{datetime.now()}] Cached {len(all_politicians)} politicians")
        return True
        
    except Exception as e:
        cache['politicians']['loading'] = False
        print(f"[{datetime.now()}] Error updating politicians cache: {e}")
        return False

def load_all_bills():
    """Load all bills from the API"""
    all_bills = []
    offset = 0
    limit = 100
    
    while True:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/bills/',
            params={'limit': limit, 'offset': offset},
            headers=HEADERS
        )
        response.raise_for_status()
        data = response.json()
        
        all_bills.extend(data['objects'])
        
        if not data['pagination']['next_url']:
            break
            
        offset += limit
        
        # Safety break to avoid infinite loops
        if offset > 5000:
            break
    
    return all_bills

def update_bills_cache():
    """Update the bills cache"""
    try:
        if cache['bills']['loading']:
            return False
            
        cache['bills']['loading'] = True
        print(f"[{datetime.now()}] Loading bills from API...")
        
        all_bills = load_all_bills()
        
        cache['bills']['data'] = all_bills
        cache['bills']['expires'] = time.time() + CACHE_DURATION
        cache['bills']['loading'] = False
        
        # Save to file
        save_cache_to_file({
            'data': all_bills,
            'expires': cache['bills']['expires'],
            'updated': datetime.now().isoformat()
        }, BILLS_CACHE_FILE)
        
        print(f"[{datetime.now()}] Cached {len(all_bills)} bills")
        return True
        
    except Exception as e:
        cache['bills']['loading'] = False
        print(f"[{datetime.now()}] Error updating bills cache: {e}")
        return False

@app.route('/api/politicians')
def get_politicians():
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    try:
        # Check if cache is valid
        if not is_cache_valid('politicians'):
            success = update_politicians_cache()
            if not success and cache['politicians']['data'] is None:
                return jsonify({'error': 'Failed to load politicians data'}), 500
        
        all_politicians = cache['politicians']['data']
        
        # Apply pagination
        paginated_politicians = all_politicians[offset:offset + limit]
        
        # Build response in same format as original API
        has_next = (offset + limit) < len(all_politicians)
        next_url = f"/politicians/?limit={limit}&offset={offset + limit}" if has_next else None
        prev_url = f"/politicians/?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
        
        return jsonify({
            'objects': paginated_politicians,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'next_url': next_url,
                'previous_url': prev_url
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/politicians/<path:politician_path>')
def get_politician(politician_path):
    try:
        # Only serve from cached politicians data
        if cache['politicians']['data']:
            # Find the politician in our cached data
            politician_url = f'/politicians/{politician_path}/'
            for politician in cache['politicians']['data']:
                if politician['url'] == politician_url:
                    print(f"[{datetime.now()}] Serving politician {politician_path} from cache")
                    return jsonify(politician)
        
        # No cached data available
        print(f"[{datetime.now()}] Politician {politician_path} not found in cache")
        return jsonify({
            'error': 'Politician not found in cache',
            'message': 'This politician is not available in our cached data.',
            'politician_path': politician_path
        }), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/ballots')
def get_vote_ballots():
    vote_url = request.args.get('vote')
    limit = int(request.args.get('limit', 400))
    offset = int(request.args.get('offset', 0))
    
    if not vote_url:
        return jsonify({'error': 'vote parameter is required'}), 400
    
    try:
        # Only serve from cached vote details data
        # Convert vote URL to path for cache lookup
        if vote_url.startswith('/votes/'):
            # Extract session and number from /votes/44-1/451/ -> 44-1_451
            parts = vote_url.replace('/votes/', '').strip('/').split('/')
            if len(parts) >= 2:
                vote_path = f"{parts[0]}_{parts[1]}"
            else:
                vote_path = vote_url.replace('/votes/', '').replace('/', '')
        else:
            vote_path = vote_url
        print(f"[{datetime.now()}] Looking for vote ballots: {vote_url} -> {vote_path}")
        
        cached_data = load_cached_vote_details(vote_path)
        if cached_data and 'ballots' in cached_data:
            ballots = cached_data['ballots']
            
            # Apply pagination
            end_index = offset + limit
            paginated_ballots = ballots[offset:end_index]
            
            print(f"[{datetime.now()}] Serving {len(paginated_ballots)} ballots for {vote_path} from cache")
            
            return jsonify({
                'objects': paginated_ballots,
                'meta': {
                    'limit': limit,
                    'offset': offset,
                    'total_count': len(ballots)
                }
            })
        
        # No cached data available
        print(f"[{datetime.now()}] Vote ballots for {vote_path} not available in cache")
        return jsonify({
            'error': 'Vote ballots not cached',
            'message': 'Ballots for this vote have not been cached yet. Background caching scripts will update this data.',
            'vote_url': vote_url
        }), 404
        
    except Exception as e:
        print(f"[{datetime.now()}] Error serving vote ballots for {vote_url}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/politician/<path:politician_path>/votes')
def get_politician_votes(politician_path):
    limit = int(request.args.get('limit', 1000))  # Allow large limits for cached data
    offset = int(request.args.get('offset', 0))
    
    try:
        # Check if MP votes are already in memory cache and valid
        if (politician_path in cache['mp_votes'] and 
            cache['mp_votes'][politician_path]['data'] is not None and 
            time.time() < cache['mp_votes'][politician_path]['expires']):
            
            all_cached_votes = cache['mp_votes'][politician_path]['data']
            
            # Apply pagination to cached data
            end_index = offset + limit
            paginated_votes = all_cached_votes[offset:end_index]
            has_more = end_index < len(all_cached_votes)
            
            print(f"[{datetime.now()}] Serving {len(paginated_votes)} cached votes for {politician_path} (offset: {offset}, total cached: {len(all_cached_votes)})")
            
            return jsonify({
                'objects': paginated_votes,
                'pagination': {
                    'offset': offset,
                    'limit': limit,
                    'next_url': None,
                    'previous_url': None
                },
                'cached': True,
                'total_cached': len(all_cached_votes),
                'has_more': has_more
            })
        
        # Try loading MP votes from cache file on-demand
        if load_mp_votes_on_demand(politician_path):
            all_cached_votes = cache['mp_votes'][politician_path]['data']
            
            # Apply pagination to newly loaded data
            end_index = offset + limit
            paginated_votes = all_cached_votes[offset:end_index]
            has_more = end_index < len(all_cached_votes)
            
            print(f"[{datetime.now()}] Serving {len(paginated_votes)} on-demand loaded votes for {politician_path} (total: {len(all_cached_votes)})")
            
            return jsonify({
                'objects': paginated_votes,
                'pagination': {
                    'offset': offset,
                    'limit': limit,
                    'next_url': None,
                    'previous_url': None
                },
                'cached': True,
                'total_cached': len(all_cached_votes),
                'has_more': has_more,
                'source': 'on_demand_cache'
            })
        
        # Check if currently being cached in background
        if (politician_path in cache['mp_votes'] and 
            cache['mp_votes'][politician_path].get('loading', False)):
            
            return jsonify({
                'objects': [],
                'pagination': {'offset': 0, 'limit': limit, 'next_url': None, 'previous_url': None},
                'loading': True,
                'cached': False,
                'message': 'Voting records are being cached in the background, please refresh in a moment'
            })
        
        # Try to build from comprehensive cache
        print(f"[{datetime.now()}] Building voting records for {politician_path} from comprehensive cache...")
        comprehensive_votes = build_mp_votes_from_comprehensive_cache(politician_path)
        
        if comprehensive_votes:
            # Apply pagination to comprehensive data
            end_index = offset + limit
            paginated_votes = comprehensive_votes[offset:end_index]
            has_more = end_index < len(comprehensive_votes)
            
            print(f"[{datetime.now()}] Serving {len(paginated_votes)} votes for {politician_path} from comprehensive cache (total: {len(comprehensive_votes)})")
            
            return jsonify({
                'objects': paginated_votes,
                'pagination': {
                    'offset': offset,
                    'limit': limit,
                    'next_url': None,
                    'previous_url': None
                },
                'cached': True,
                'total_cached': len(comprehensive_votes),
                'has_more': has_more,
                'source': 'comprehensive_cache'
            })
        
        # No data available anywhere
        print(f"[{datetime.now()}] No voting data available for {politician_path}")
        return jsonify({
            'objects': [],
            'pagination': {'offset': 0, 'limit': limit, 'next_url': None, 'previous_url': None},
            'cached': False,
            'total_cached': 0,
            'message': 'No voting records available for this MP.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/<path:vote_path>/details')
def get_vote_details(vote_path):
    try:
        # Only serve from cached data - never call external API
        cached_data = load_cached_vote_details(vote_path)
        if cached_data:
            enriched_data = enrich_cached_vote_details(cached_data)
            if enriched_data:
                print(f"[{datetime.now()}] Serving vote details for {vote_path} from cache")
                return jsonify(enriched_data)
        
        # No cached data available
        print(f"[{datetime.now()}] Vote details for {vote_path} not available in cache")
        return jsonify({
            'error': 'Vote details not cached',
            'message': 'This vote has not been cached yet. Background caching scripts will update this data.',
            'vote_path': vote_path,
            'from_cache': False
        }), 404
        
    except Exception as e:
        print(f"[{datetime.now()}] Error serving vote details for {vote_path}: {e}")
        return jsonify({'error': str(e)}), 500

def load_comprehensive_votes():
    """Load all cached votes from the comprehensive cache"""
    try:
        # Try to load from comprehensive cache first
        if os.path.exists(VOTE_CACHE_INDEX_FILE):
            with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
                index_data = json.load(f)
            
            # Extract vote list from cached votes
            cached_votes = index_data.get('cached_votes', {})
            all_votes = []
            
            # Convert cached vote index to full vote objects
            for vote_id, vote_info in cached_votes.items():
                try:
                    # Load the full vote details from cache file
                    vote_cache_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
                    if os.path.exists(vote_cache_file):
                        with open(vote_cache_file, 'r') as f:
                            vote_details = json.load(f)
                        
                        vote_data = vote_details.get('vote', {})
                        # Ensure all expected fields exist with proper defaults
                        vote_obj = {
                            'url': vote_data.get('url', vote_info['url']),
                            'session': vote_data.get('session', ''),
                            'number': vote_data.get('number', 0),
                            'date': vote_data.get('date', ''),
                            'description': vote_data.get('description', {}),
                            'result': vote_data.get('result', ''),
                            'bill_url': vote_data.get('bill_url'),  # Can be None
                            'yea_total': vote_data.get('yea_total', 0),
                            'nay_total': vote_data.get('nay_total', 0),
                            'paired_total': vote_data.get('paired_total', 0)
                        }
                        all_votes.append(vote_obj)
                except Exception as e:
                    print(f"Error loading vote details for {vote_id}: {e}")
                    continue
            
            # Sort by session and number (newest first)
            all_votes.sort(key=lambda x: (x['session'], x['number']), reverse=True)
            
            print(f"Loaded {len(all_votes)} votes from comprehensive cache")
            return all_votes
            
    except Exception as e:
        print(f"Error loading comprehensive votes cache: {e}")
    
    # Fallback to recent votes API if comprehensive cache fails
    try:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/',
            params={'limit': 100, 'offset': 0},
            headers=HEADERS
        )
        response.raise_for_status()
        return response.json()['objects']
    except Exception as e:
        print(f"Error loading votes from API: {e}")
        return []

def build_mp_votes_from_comprehensive_cache(mp_slug):
    """Build MP voting records from comprehensive vote cache"""
    try:
        if not os.path.exists(VOTE_CACHE_INDEX_FILE):
            return []
            
        with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
            index_data = json.load(f)
        
        cached_votes = index_data.get('cached_votes', {})
        mp_votes = []
        mp_url = f'/politicians/{mp_slug}/'
        
        # Check each cached vote for this MP's ballot
        for vote_id, vote_info in cached_votes.items():
            try:
                # Load the detailed vote cache file
                vote_cache_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
                if os.path.exists(vote_cache_file):
                    with open(vote_cache_file, 'r') as f:
                        vote_details = json.load(f)
                    
                    # Find this MP's ballot in the vote
                    for ballot in vote_details.get('ballots', []):
                        if ballot.get('politician_url') == mp_url:
                            # Build vote record with MP's ballot - ensure all expected fields exist
                            vote_data = vote_details.get('vote', {})
                            vote_record = {
                                'url': vote_data.get('url', ''),
                                'date': vote_data.get('date', ''),
                                'number': vote_data.get('number', ''),
                                'session': vote_data.get('session', ''),
                                'result': vote_data.get('result', ''),
                                'description': vote_data.get('description', {}),
                                'bill_url': vote_data.get('bill_url'),  # Can be null
                                'yea_total': vote_data.get('yea_total', 0),
                                'nay_total': vote_data.get('nay_total', 0),
                                'paired_total': vote_data.get('paired_total', 0),
                                'mp_ballot': ballot.get('ballot', 'Unknown')
                            }
                            mp_votes.append(vote_record)
                            break
                            
            except Exception as e:
                print(f"Error processing vote {vote_id} for {mp_slug}: {e}")
                continue
        
        # Sort by date descending
        mp_votes.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        print(f"[{datetime.now()}] Built {len(mp_votes)} votes for {mp_slug} from comprehensive cache")
        return mp_votes
        
    except Exception as e:
        print(f"Error building MP votes from comprehensive cache for {mp_slug}: {e}")
        return []

def update_votes_cache():
    """Update the votes cache"""
    try:
        if cache['votes']['loading']:
            return False
            
        cache['votes']['loading'] = True
        print(f"[{datetime.now()}] Loading votes from comprehensive cache...")
        
        comprehensive_votes = load_comprehensive_votes()
        
        cache['votes']['data'] = comprehensive_votes
        cache['votes']['expires'] = time.time() + CACHE_DURATION
        cache['votes']['loading'] = False
        
        # Save to file
        save_cache_to_file({
            'data': comprehensive_votes,
            'expires': cache['votes']['expires'],
            'updated': datetime.now().isoformat(),
            'count': len(comprehensive_votes)
        }, VOTES_CACHE_FILE)
        
        print(f"[{datetime.now()}] Cached {len(comprehensive_votes)} votes from comprehensive cache")
        
        # Start background caching of MP votes
        start_background_mp_votes_caching()
        
        return True
        
    except Exception as e:
        cache['votes']['loading'] = False
        print(f"[{datetime.now()}] Error updating votes cache: {e}")
        return False

def fetch_mp_details_from_api(mp_slug):
    """Fetch MP details from Parliament API for MPs not in current cache"""
    # Check if already cached
    if mp_slug in cache['mp_details']:
        cached_data = cache['mp_details'][mp_slug]
        if time.time() < cached_data['expires']:
            return cached_data['data']
    
    try:
        print(f"[{datetime.now()}] Fetching MP details from API for {mp_slug}")
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/politicians/{mp_slug}/',
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        mp_data = response.json()
        
        # Cache for 1 hour
        cache['mp_details'][mp_slug] = {
            'data': mp_data,
            'expires': time.time() + 3600
        }
        
        print(f"[{datetime.now()}] Successfully fetched and cached details for {mp_data.get('name', mp_slug)}")
        return mp_data
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching MP details for {mp_slug}: {e}")
        # Cache empty result for 10 minutes to avoid repeated failures
        cache['mp_details'][mp_slug] = {
            'data': {},
            'expires': time.time() + 600
        }
        return {}

def get_mp_voting_records_from_api(mp_slug, limit=20, offset=0):
    """Get voting records for a specific MP directly from Parliament API (for pagination beyond cache)"""
    try:
        print(f"[{datetime.now()}] Fetching votes from API for {mp_slug} (limit: {limit}, offset: {offset})")
        
        # Get ballots for this politician directly from Parliament API
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'politician': f'/politicians/{mp_slug}/',
                'limit': limit,
                'offset': offset
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
                    ballot = all_ballots[i + j]
                    future = executor.submit(fetch_vote_details, vote_url, ballot['ballot'])
                    future_to_ballot[future] = ballot
                
                for future in as_completed(future_to_ballot):
                    try:
                        vote_data = future.result(timeout=10)
                        if vote_data:
                            votes_with_ballots.append(vote_data)
                    except Exception as e:
                        print(f"Error processing vote: {e}")
                        continue
            
            # Small delay between batches
            time.sleep(0.1)
        
        # Sort by date descending
        votes_with_ballots.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        print(f"[{datetime.now()}] Fetched {len(votes_with_ballots)} votes from API for {mp_slug}")
        return votes_with_ballots
        
    except Exception as e:
        print(f"[{datetime.now()}] Error getting MP voting records from API for {mp_slug}: {e}")
        return []

def get_mp_voting_records(mp_slug, limit=300):
    """Get voting records for a specific MP"""
    try:
        # Get all ballots for this politician with pagination
        all_ballots = []
        offset = 0
        limit_per_request = 100  # API seems to limit to 100 per request
        
        while True:
            response = requests.get(
                f'{PARLIAMENT_API_BASE}/votes/ballots/',
                params={
                    'politician': f'/politicians/{mp_slug}/',
                    'limit': limit_per_request,
                    'offset': offset
                },
                headers=HEADERS,
                timeout=30
            )
            response.raise_for_status()
            ballots_data = response.json()
            
            ballots = ballots_data.get('objects', [])
            if not ballots:
                break
                
            all_ballots.extend(ballots)
            
            # Stop if we have enough votes or if we got fewer than requested (last page)
            if len(ballots) < limit_per_request or len(all_ballots) >= limit:
                break
                
            offset += limit_per_request
            time.sleep(0.1)  # Be nice to the API
        
        # Limit to requested amount
        if len(all_ballots) > limit:
            all_ballots = all_ballots[:limit]
        
        print(f"[{datetime.now()}] Fetched {len(all_ballots)} ballots for {mp_slug}")
        
        # For each ballot, get the vote details (batch process)
        votes_with_ballots = []
        vote_urls = [ballot['vote_url'] for ballot in all_ballots]
        
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
                        print(f"Error processing vote: {e}")
                        continue
            
            # Small delay between batches
            time.sleep(0.1)
        
        # Sort by date descending
        votes_with_ballots.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return votes_with_ballots[:limit]  # Return up to specified limit
        
    except Exception as e:
        print(f"Error getting MP voting records for {mp_slug}: {e}")
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
        print(f"Error fetching vote details for {vote_url}: {e}")
        return None

def cache_mp_votes_background(mp_slug):
    """Cache voting records for a specific MP in background"""
    try:
        if mp_slug in cache['mp_votes'] and cache['mp_votes'][mp_slug].get('loading', False):
            return
            
        cache['mp_votes'][mp_slug] = {'loading': True, 'data': None, 'expires': 0}
        
        print(f"[{datetime.now()}] Background caching votes for {mp_slug}")
        votes = get_mp_voting_records(mp_slug, 1000)  # Increased to 1000 to capture all session 44-1 votes (928 total)
        
        expires_time = time.time() + CACHE_DURATION
        cache['mp_votes'][mp_slug] = {
            'data': votes,
            'expires': expires_time,
            'loading': False
        }
        
        # Save to file
        mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
        save_cache_to_file({
            'data': votes,
            'expires': expires_time,
            'updated': datetime.now().isoformat()
        }, mp_cache_file)
        
        print(f"[{datetime.now()}] Cached {len(votes)} votes for {mp_slug}")
        
    except Exception as e:
        print(f"[{datetime.now()}] Error caching votes for {mp_slug}: {e}")
        if mp_slug in cache['mp_votes']:
            cache['mp_votes'][mp_slug]['loading'] = False

def start_background_mp_votes_caching():
    """Start minimal background caching for top 10 MPs only"""
    def background_task():
        try:
            if not cache['politicians']['data']:
                return
                
            # Cache only first 10 MPs to reduce memory usage
            popular_mps = cache['politicians']['data'][:10]
            
            print(f"[{datetime.now()}] Starting minimal background caching for {len(popular_mps)} MPs")
            
            for mp in popular_mps:
                mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
                
                # Check if already in memory cache
                if (mp_slug in cache['mp_votes'] and 
                    cache['mp_votes'][mp_slug]['data'] is not None and 
                    time.time() < cache['mp_votes'][mp_slug]['expires']):
                    continue
                
                # Use on-demand loading instead of API calls
                mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
                if os.path.exists(mp_cache_file):
                    load_mp_votes_on_demand(mp_slug)
                    print(f"[{datetime.now()}] Pre-loaded cache for popular MP: {mp_slug}")
                    
                    # Longer delay to reduce memory pressure
                    time.sleep(2.0)
                
        except Exception as e:
            print(f"[{datetime.now()}] Error in background MP votes caching: {e}")
    
    # Run in background thread with delay
    def delayed_start():
        time.sleep(60)  # Wait 60 seconds after startup
        background_task()
    
    threading.Thread(target=delayed_start, daemon=True).start()

@app.route('/api/votes')
def get_votes():
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    
    try:
        # Check if cache is valid
        if not is_cache_valid('votes'):
            success = update_votes_cache()
            if not success and cache['votes']['data'] is None:
                return jsonify({'error': 'Failed to load votes data'}), 500
        
        all_votes = cache['votes']['data']
        
        # Apply pagination
        paginated_votes = all_votes[offset:offset + limit]
        
        # Build response in same format as original API
        has_next = (offset + limit) < len(all_votes)
        next_url = f"/votes/?limit={limit}&offset={offset + limit}" if has_next else None
        prev_url = f"/votes/?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
        
        return jsonify({
            'objects': paginated_votes,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'next_url': next_url,
                'previous_url': prev_url
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills')
def get_bills():
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    session = request.args.get('session')  # Optional session filter
    sponsor = request.args.get('sponsor')  # Optional sponsor filter
    
    try:
        # Check if cache is valid
        if not is_cache_valid('bills'):
            success = update_bills_cache()
            if not success and cache['bills']['data'] is None:
                return jsonify({'error': 'Failed to load bills data'}), 500
        
        all_bills = cache['bills']['data']
        
        # Apply filters
        filtered_bills = all_bills
        if session:
            filtered_bills = [bill for bill in filtered_bills if bill.get('session') == session]
        
        if sponsor:
            # Filter by sponsor MP slug (extract from URL)
            sponsor_url = f'/politicians/{sponsor}/'
            filtered_bills = [bill for bill in filtered_bills 
                            if bill.get('sponsor_politician_url') == sponsor_url]
        
        # Sort bills by session (descending) and then by introduced date (descending)
        filtered_bills.sort(key=lambda x: (
            x.get('session') or '', 
            x.get('introduced') or ''
        ), reverse=True)
        
        # Apply pagination
        paginated_bills = filtered_bills[offset:offset + limit]
        
        # Build response in same format as original API
        has_next = (offset + limit) < len(filtered_bills)
        next_url = f"/bills/?limit={limit}&offset={offset + limit}" if has_next else None
        prev_url = f"/bills/?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
        
        return jsonify({
            'objects': paginated_bills,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'next_url': next_url,
                'previous_url': prev_url
            },
            'total_count': len(filtered_bills),
            'filters_applied': {
                'session': session,
                'sponsor': sponsor
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/<path:bill_path>')
def get_bill(bill_path):
    """Get individual bill details"""
    try:
        # Extract session and number from path like "44-1/C-1" 
        path_parts = bill_path.split('/')
        if len(path_parts) != 2:
            return jsonify({'error': 'Invalid bill path format. Expected: session/number'}), 400
            
        session, number = path_parts
        
        # Check if bills cache is valid
        if not is_cache_valid('bills'):
            success = update_bills_cache()
            if not success and cache['bills']['data'] is None:
                return jsonify({'error': 'Failed to load bills data'}), 500
        
        # Find the bill in our cached data
        for bill in cache['bills']['data']:
            if bill.get('session') == session and bill.get('number') == number:
                print(f"[{datetime.now()}] Serving bill {bill_path} from cache")
                return jsonify(bill)
        
        # Bill not found
        print(f"[{datetime.now()}] Bill {bill_path} not found in cache")
        return jsonify({
            'error': 'Bill not found',
            'message': 'This bill is not available in our cached data.',
            'bill_path': bill_path
        }), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reload-historical-mps', methods=['POST'])
def reload_historical_mps():
    """Reload historical MP data from cache file"""
    try:
        load_historical_mps()
        return jsonify({
            'success': True,
            'message': f'Reloaded {len(cache["historical_mps"]["data"])} historical MPs',
            'count': len(cache['historical_mps']['data'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
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
CACHE_DURATION = 3600  # 1 hour in seconds
CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')

# Ensure cache directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)

# In-memory cache for fast access (loaded from files)
cache = {
    'politicians': {'data': None, 'expires': 0, 'loading': False},
    'votes': {'data': None, 'expires': 0, 'loading': False},
    'mp_votes': {}  # {mp_slug: {'data': [...], 'expires': timestamp, 'loading': False}}
}

@app.route('/')
def hello():
    politicians_status = 'cached' if is_cache_valid('politicians') else 'expired/empty'
    votes_status = 'cached' if is_cache_valid('votes') else 'expired/empty'
    
    politicians_count = len(cache['politicians']['data']) if cache['politicians']['data'] else 0
    votes_count = len(cache['votes']['data']) if cache['votes']['data'] else 0
    mp_votes_count = len([k for k, v in cache['mp_votes'].items() if v.get('data')])
    mp_votes_loading = len([k for k, v in cache['mp_votes'].items() if v.get('loading', False)])
    
    politicians_expires = datetime.fromtimestamp(cache['politicians']['expires']).isoformat() if cache['politicians']['expires'] > 0 else 'N/A'
    votes_expires = datetime.fromtimestamp(cache['votes']['expires']).isoformat() if cache['votes']['expires'] > 0 else 'N/A'
    
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
            'mp_votes': {
                'cached_mps': mp_votes_count,
                'loading_mps': mp_votes_loading,
                'total_cached_records': sum(len(v.get('data', [])) for v in cache['mp_votes'].values() if v.get('data'))
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
    
    # Load MP votes
    if os.path.exists(MP_VOTES_CACHE_DIR):
        for filename in os.listdir(MP_VOTES_CACHE_DIR):
            if filename.endswith('.json'):
                mp_slug = filename[:-5]  # Remove .json extension
                mp_data = load_cache_from_file(os.path.join(MP_VOTES_CACHE_DIR, filename))
                if mp_data:
                    cache['mp_votes'][mp_slug] = {
                        'data': mp_data.get('data', []),
                        'expires': mp_data.get('expires', 0),
                        'loading': False
                    }
        print(f"[{datetime.now()}] Loaded {len(cache['mp_votes'])} MP vote caches")

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
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/politicians/{politician_path}/',
            headers=HEADERS
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/ballots')
def get_vote_ballots():
    vote_url = request.args.get('vote')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    if not vote_url:
        return jsonify({'error': 'vote parameter is required'}), 400
    
    try:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'vote': vote_url,
                'limit': limit,
                'offset': offset
            },
            headers=HEADERS
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/politician/<path:politician_path>/votes')
def get_politician_votes(politician_path):
    limit = int(request.args.get('limit', 20))
    
    try:
        # Check if we have cached data for this MP
        if (politician_path in cache['mp_votes'] and 
            cache['mp_votes'][politician_path]['data'] is not None and 
            time.time() < cache['mp_votes'][politician_path]['expires']):
            
            cached_votes = cache['mp_votes'][politician_path]['data'][:limit]
            print(f"[{datetime.now()}] Serving cached votes for {politician_path}")
            
            return jsonify({
                'objects': cached_votes,
                'pagination': {
                    'offset': 0,
                    'limit': limit,
                    'next_url': None,
                    'previous_url': None
                },
                'cached': True
            })
        
        # If not cached or loading, check if currently loading
        if (politician_path in cache['mp_votes'] and 
            cache['mp_votes'][politician_path].get('loading', False)):
            
            return jsonify({
                'objects': [],
                'pagination': {'offset': 0, 'limit': limit, 'next_url': None, 'previous_url': None},
                'loading': True,
                'message': 'Votes are being loaded in the background, please try again in a moment'
            })
        
        # Start background caching for this MP
        threading.Thread(
            target=cache_mp_votes_background, 
            args=(politician_path,), 
            daemon=True
        ).start()
        
        # Return immediate response suggesting to try again
        return jsonify({
            'objects': [],
            'pagination': {'offset': 0, 'limit': limit, 'next_url': None, 'previous_url': None},
            'loading': True,
            'message': 'Loading voting records in the background, please refresh in a few seconds'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/<path:vote_path>/details')
def get_vote_details(vote_path):
    try:
        # Get the vote details
        vote_response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/{vote_path}/',
            headers=HEADERS
        )
        vote_response.raise_for_status()
        vote_data = vote_response.json()
        
        # Get all ballots for this vote
        ballots_response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/ballots/',
            params={
                'vote': f'/votes/{vote_path}/',
                'limit': 400  # Get all MPs
            },
            headers=HEADERS
        )
        ballots_response.raise_for_status()
        ballots_data = ballots_response.json()
        
        # Get all politicians to enrich ballot data
        politicians = cache['politicians'].get('data', []) if 'politicians' in cache else []
        politician_map = {mp['url']: mp for mp in politicians} if politicians else {}
        
        # Enrich ballots with MP details
        enriched_ballots = []
        for ballot in ballots_data['objects']:
            mp_data = politician_map.get(ballot['politician_url'], {})
            enriched_ballot = {
                **ballot,
                'mp_name': mp_data.get('name', 'Unknown'),
                'mp_party': mp_data.get('current_party', {}).get('short_name', {}).get('en', 'Unknown'),
                'mp_riding': mp_data.get('current_riding', {}).get('name', {}).get('en', 'Unknown'),
                'mp_province': mp_data.get('current_riding', {}).get('province', 'Unknown'),
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
        
        return jsonify({
            'vote': vote_data,
            'ballots': enriched_ballots,
            'party_stats': party_stats,
            'total_ballots': len(enriched_ballots)
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

def load_recent_votes():
    """Load recent votes from the API"""
    try:
        response = requests.get(
            f'{PARLIAMENT_API_BASE}/votes/',
            params={'limit': 100, 'offset': 0},
            headers=HEADERS
        )
        response.raise_for_status()
        return response.json()['objects']
    except Exception as e:
        print(f"Error loading votes: {e}")
        return []

def update_votes_cache():
    """Update the votes cache"""
    try:
        if cache['votes']['loading']:
            return False
            
        cache['votes']['loading'] = True
        print(f"[{datetime.now()}] Loading votes from API...")
        
        recent_votes = load_recent_votes()
        
        cache['votes']['data'] = recent_votes
        cache['votes']['expires'] = time.time() + CACHE_DURATION
        cache['votes']['loading'] = False
        
        # Save to file
        save_cache_to_file({
            'data': recent_votes,
            'expires': cache['votes']['expires'],
            'updated': datetime.now().isoformat()
        }, VOTES_CACHE_FILE)
        
        print(f"[{datetime.now()}] Cached {len(recent_votes)} votes")
        
        # Start background caching of MP votes
        start_background_mp_votes_caching()
        
        return True
        
    except Exception as e:
        cache['votes']['loading'] = False
        print(f"[{datetime.now()}] Error updating votes cache: {e}")
        return False

def get_mp_voting_records(mp_slug, limit=20):
    """Get voting records for a specific MP"""
    try:
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
                        print(f"Error processing vote: {e}")
                        continue
            
            # Small delay between batches
            time.sleep(0.1)
        
        # Sort by date descending
        votes_with_ballots.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return votes_with_ballots[:limit]
        
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
        votes = get_mp_voting_records(mp_slug, 20)
        
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
    """Start background caching of MP votes for popular MPs"""
    def background_task():
        try:
            if not cache['politicians']['data']:
                return
                
            # Cache votes for first 50 MPs (most likely to be viewed)
            popular_mps = cache['politicians']['data'][:50]
            
            print(f"[{datetime.now()}] Starting background caching for {len(popular_mps)} MPs")
            
            for mp in popular_mps:
                mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
                
                # Check if already cached and valid
                if (mp_slug in cache['mp_votes'] and 
                    cache['mp_votes'][mp_slug]['data'] is not None and 
                    time.time() < cache['mp_votes'][mp_slug]['expires']):
                    continue
                
                # Cache this MP's votes
                cache_mp_votes_background(mp_slug)
                
                # Small delay between MPs to avoid overwhelming the API
                time.sleep(0.5)
                
        except Exception as e:
            print(f"[{datetime.now()}] Error in background MP votes caching: {e}")
    
    # Run in background thread
    threading.Thread(target=background_task, daemon=True).start()

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
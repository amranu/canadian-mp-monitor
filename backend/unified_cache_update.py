#!/usr/bin/env python3
"""
Unified Cache Update Script for Canadian MP Monitor

This script replaces the existing 4-script cache system with a single, 
intelligent, and efficient cache management solution that:

1. Performs smart incremental updates for all data types
2. Manages memory efficiently for large datasets
3. Coordinates API usage to prevent rate limiting
4. Provides comprehensive progress tracking
5. Handles dependencies between different cache types

Replaces:
- update_cache.py
- incremental_update.py
- cache_all_votes.py
- cache_mp_voting_records.py
- fetch_historical_mps.py
"""

import requests
import json
import os
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional, Tuple
import argparse
import logging

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Monitor-Unified-Cache/2.0 (contact@mptracker.ca)',
    'API-Version': 'v1'
}

# Cache configuration
CACHE_DIR = 'cache'
CACHE_DURATIONS = {
    'politicians': 14400,     # 4 hours - MPs don't change often
    'votes': 3600,           # 1 hour - votes happen frequently
    'bills': 21600,          # 6 hours - bills change less frequently
    'vote_details': 86400,   # 24 hours - vote details are immutable
    'mp_votes': 7200,        # 2 hours - MP voting records
    'historical_mps': 604800 # 1 week - historical data changes rarely
}

# Cache file paths
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
BILLS_CACHE_FILE = os.path.join(CACHE_DIR, 'bills.json')
BILLS_WITH_VOTES_INDEX_FILE = os.path.join(CACHE_DIR, 'bills_with_votes_index.json')
VOTE_DETAILS_CACHE_DIR = os.path.join(CACHE_DIR, 'vote_details')
VOTE_CACHE_INDEX_FILE = os.path.join(CACHE_DIR, 'vote_cache_index.json')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')
HISTORICAL_MPS_CACHE_FILE = os.path.join(CACHE_DIR, 'historical_mps.json')
STATISTICS_FILE = os.path.join(CACHE_DIR, 'unified_cache_statistics.json')

# API rate limiting
API_DELAY_BETWEEN_REQUESTS = 0.2  # 200ms delay between requests
API_DELAY_BETWEEN_BATCHES = 1.0   # 1 second delay between batches
MAX_CONCURRENT_WORKERS = 3        # Max concurrent API requests

class UnifiedCacheUpdater:
    def __init__(self, mode='auto', force_full=False, log_level='INFO'):
        """
        Initialize the unified cache updater
        
        Args:
            mode: 'auto', 'incremental', 'full', or 'specific'
            force_full: Force full update even if cache is fresh
            log_level: Logging level
        """
        self.mode = mode
        self.force_full = force_full
        self.stats = {
            'start_time': datetime.now(),
            'operations': {},
            'api_calls': 0,
            'errors': [],
            'cache_sizes': {}
        }
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='[%(asctime)s] %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(CACHE_DIR, 'unified_cache.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.ensure_cache_dirs()
        
    def ensure_cache_dirs(self):
        """Ensure all cache directories exist"""
        os.makedirs(CACHE_DIR, exist_ok=True)
        os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)
        os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)
        
    def log_operation(self, operation: str, status: str, details: str = ""):
        """Log operation with structured format"""
        self.logger.info(f"{operation}: {status} {details}")
        self.stats['operations'][operation] = {
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
    def is_cache_expired(self, cache_file: str, cache_type: str) -> bool:
        """Check if cache file is expired based on type-specific duration"""
        if self.force_full:
            return True
            
        if not os.path.exists(cache_file):
            return True
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            expires = data.get('expires', 0)
            return time.time() > expires
            
        except (json.JSONDecodeError, KeyError):
            return True
    
    def save_cache_data(self, data: dict, cache_file: str, cache_type: str) -> bool:
        """Save cache data with expiration timestamp"""
        try:
            cache_data = {
                'data': data,
                'expires': time.time() + CACHE_DURATIONS[cache_type],
                'updated': datetime.now().isoformat(),
                'count': len(data) if isinstance(data, list) else len(data.get('objects', []))
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            file_size = os.path.getsize(cache_file)
            self.stats['cache_sizes'][cache_type] = file_size
            self.logger.info(f"Saved {cache_type} cache: {cache_data['count']} items, {file_size // 1024}KB")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving {cache_type} cache: {e}")
            self.stats['errors'].append(f"Save {cache_type}: {e}")
            return False
    
    def api_request(self, url: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
        """Make API request with rate limiting and error handling"""
        self.stats['api_calls'] += 1
        
        try:
            time.sleep(API_DELAY_BETWEEN_REQUESTS)
            response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"API request failed: {url} - {e}")
            self.stats['errors'].append(f"API {url}: {e}")
            return None
    
    def update_politicians_cache(self) -> bool:
        """Update politicians cache with all current MPs"""
        self.log_operation("Politicians Cache", "STARTED")
        
        if not self.is_cache_expired(POLITICIANS_CACHE_FILE, 'politicians'):
            self.log_operation("Politicians Cache", "SKIPPED", "Cache still fresh")
            return True
            
        all_politicians = []
        offset = 0
        limit = 100
        
        while True:
            data = self.api_request(f'{PARLIAMENT_API_BASE}/politicians/', {
                'limit': limit, 'offset': offset
            })
            
            if not data or not data.get('objects'):
                break
                
            all_politicians.extend(data['objects'])
            self.logger.info(f"Loaded {len(data['objects'])} politicians (total: {len(all_politicians)})")
            
            if not data.get('pagination', {}).get('next_url'):
                break
                
            offset += limit
            
            # Safety break
            if offset > 1000:
                self.logger.warning("Politicians: Safety break at offset 1000")
                break
        
        if all_politicians:
            success = self.save_cache_data(all_politicians, POLITICIANS_CACHE_FILE, 'politicians')
            self.log_operation("Politicians Cache", "COMPLETED" if success else "FAILED", 
                             f"{len(all_politicians)} MPs")
            return success
        
        self.log_operation("Politicians Cache", "FAILED", "No data retrieved")
        return False
    
    def get_vote_cache_index(self) -> Tuple[Dict, Set]:
        """Load existing vote cache index and return cached vote IDs"""
        try:
            if os.path.exists(VOTE_CACHE_INDEX_FILE):
                with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
                    index_data = json.load(f)
                cached_votes = set(index_data.get('cached_votes', {}).keys())
                return index_data, cached_votes
        except Exception as e:
            self.logger.warning(f"Could not load vote cache index: {e}")
            
        return {'cached_votes': {}, 'updated': datetime.now().isoformat()}, set()
    
    def update_votes_cache(self) -> bool:
        """Update recent votes cache"""
        self.log_operation("Votes Cache", "STARTED")
        
        if not self.is_cache_expired(VOTES_CACHE_FILE, 'votes'):
            self.log_operation("Votes Cache", "SKIPPED", "Cache still fresh")
            return True
            
        data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/', {
            'limit': 100, 'offset': 0
        })
        
        if data and data.get('objects'):
            success = self.save_cache_data(data['objects'], VOTES_CACHE_FILE, 'votes')
            self.log_operation("Votes Cache", "COMPLETED" if success else "FAILED", 
                             f"{len(data['objects'])} votes")
            return success
        
        self.log_operation("Votes Cache", "FAILED", "No data retrieved")
        return False
    
    def update_vote_details_incremental(self) -> bool:
        """Update vote details incrementally - only fetch new votes"""
        self.log_operation("Vote Details Incremental", "STARTED")
        
        # Get current vote cache index
        index_data, cached_vote_ids = self.get_vote_cache_index()
        
        # Get recent votes to check for new ones
        recent_votes_data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/', {
            'limit': 200, 'offset': 0
        })
        
        if not recent_votes_data or not recent_votes_data.get('objects'):
            self.log_operation("Vote Details Incremental", "FAILED", "No votes data")
            return False
        
        # Find new votes not in cache
        new_votes = []
        for vote in recent_votes_data['objects']:
            # Convert /votes/45-1/4/ to 45-1_4 (compatible with existing cache format)
            vote_id = vote['url'].replace('/votes/', '').replace('/', '_').rstrip('_')
            if vote_id not in cached_vote_ids:
                new_votes.append((vote_id, vote))
        
        if not new_votes:
            self.log_operation("Vote Details Incremental", "COMPLETED", "No new votes found")
            return True
        
        self.logger.info(f"Found {len(new_votes)} new votes to cache")
        
        # Process new votes in batches
        successful_updates = 0
        batch_size = 5
        
        for i in range(0, len(new_votes), batch_size):
            batch = new_votes[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
                future_to_vote = {}
                
                for vote_id, vote in batch:
                    future = executor.submit(self._cache_single_vote_details, vote_id, vote)
                    future_to_vote[future] = (vote_id, vote)
                
                for future in as_completed(future_to_vote):
                    vote_id, vote = future_to_vote[future]
                    try:
                        success = future.result(timeout=30)
                        if success:
                            successful_updates += 1
                            # Update index
                            index_data['cached_votes'][vote_id] = {
                                'url': vote['url'],
                                'date': vote.get('date'),
                                'cached_at': datetime.now().isoformat()
                            }
                    except Exception as e:
                        self.logger.error(f"Error processing vote {vote_id}: {e}")
            
            # Delay between batches
            time.sleep(API_DELAY_BETWEEN_BATCHES)
        
        # Save updated index
        index_data['updated'] = datetime.now().isoformat()
        index_data['total_cached'] = len(index_data['cached_votes'])
        
        try:
            with open(VOTE_CACHE_INDEX_FILE, 'w') as f:
                json.dump(index_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving vote cache index: {e}")
        
        self.log_operation("Vote Details Incremental", "COMPLETED", 
                         f"{successful_updates}/{len(new_votes)} new votes cached")
        return successful_updates > 0
    
    def _cache_single_vote_details(self, vote_id: str, vote: dict) -> bool:
        """Cache details for a single vote including ballots"""
        try:
            # Get vote details
            vote_details = self.api_request(f"{PARLIAMENT_API_BASE}{vote['url']}")
            if not vote_details:
                return False
            
            # Get ballots for this vote
            ballots_data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/ballots/', {
                'vote': vote['url'],
                'limit': 400
            })
            
            # Combine data
            combined_data = {
                'vote': vote_details,
                'ballots': ballots_data.get('objects', []) if ballots_data else [],
                'cached_at': datetime.now().isoformat()
            }
            
            # Save to individual file
            vote_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
            with open(vote_file, 'w') as f:
                json.dump(combined_data, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching vote {vote_id}: {e}")
            return False
    
    def update_bills_cache(self) -> bool:
        """Update bills cache with all parliamentary bills"""
        self.log_operation("Bills Cache", "STARTED")
        
        if not self.is_cache_expired(BILLS_CACHE_FILE, 'bills'):
            self.log_operation("Bills Cache", "SKIPPED", "Cache still fresh")
            return True
            
        all_bills = []
        offset = 0
        limit = 100
        
        while True:
            data = self.api_request(f'{PARLIAMENT_API_BASE}/bills/', {
                'limit': limit, 'offset': offset
            })
            
            if not data or not data.get('objects'):
                break
                
            all_bills.extend(data['objects'])
            self.logger.info(f"Loaded {len(data['objects'])} bills (total: {len(all_bills)})")
            
            if not data.get('pagination', {}).get('next_url'):
                break
                
            offset += limit
            
            # Safety break
            if offset > 5000:
                self.logger.warning("Bills: Safety break at offset 5000")
                break
        
        if all_bills:
            success = self.save_cache_data(all_bills, BILLS_CACHE_FILE, 'bills')
            if success:
                self._build_bills_with_votes_index()
            self.log_operation("Bills Cache", "COMPLETED" if success else "FAILED", 
                             f"{len(all_bills)} bills")
            return success
        
        self.log_operation("Bills Cache", "FAILED", "No data retrieved")
        return False
    
    def _build_bills_with_votes_index(self):
        """Build index of bills that have associated votes"""
        try:
            self.logger.info("Building bills with votes index...")
            bills_with_votes = set()
            
            if os.path.exists(VOTE_CACHE_INDEX_FILE):
                with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
                    index_data = json.load(f)
                
                cached_votes = index_data.get('cached_votes', {})
                
                for vote_id in cached_votes:
                    vote_cache_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
                    if os.path.exists(vote_cache_file):
                        try:
                            with open(vote_cache_file, 'r') as f:
                                vote_details = json.load(f)
                            
                            bill_url = vote_details.get('vote', {}).get('bill_url')
                            if bill_url:
                                bills_with_votes.add(bill_url)
                        except Exception:
                            continue
            
            index_data = {
                'bills_with_votes': list(bills_with_votes),
                'updated': datetime.now().isoformat(),
                'count': len(bills_with_votes)
            }
            
            with open(BILLS_WITH_VOTES_INDEX_FILE, 'w') as f:
                json.dump(index_data, f, indent=2)
                
            self.logger.info(f"Built bills with votes index: {len(bills_with_votes)} bills")
            
        except Exception as e:
            self.logger.error(f"Error building bills with votes index: {e}")
    
    def update_mp_voting_records(self, max_mps: int = None) -> bool:
        """Build MP voting records from cached vote data (memory efficient)"""
        self.log_operation("MP Voting Records", "STARTED")
        
        # Load politicians
        try:
            with open(POLITICIANS_CACHE_FILE, 'r') as f:
                politicians_data = json.load(f)
            politicians = politicians_data.get('data', [])
        except Exception as e:
            self.log_operation("MP Voting Records", "FAILED", f"Cannot load politicians: {e}")
            return False
        
        # Create temporary working directory
        temp_dir = tempfile.mkdtemp(prefix='mp_votes_')
        
        try:
            successful_updates = 0
            
            # Process MPs in batches to manage memory
            mps_to_process = politicians if max_mps is None else politicians[:max_mps]
            for i, mp in enumerate(mps_to_process):
                mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
                
                if self._is_mp_votes_cache_fresh(mp_slug):
                    continue
                
                votes = self._build_mp_votes_from_cache(mp_slug, temp_dir)
                
                if votes:
                    cache_data = {
                        'data': votes,
                        'expires': time.time() + CACHE_DURATIONS['mp_votes'],
                        'updated': datetime.now().isoformat(),
                        'mp_name': mp.get('name', 'Unknown'),
                        'count': len(votes)
                    }
                    
                    mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
                    try:
                        with open(mp_cache_file, 'w') as f:
                            json.dump(cache_data, f, indent=2)
                        successful_updates += 1
                        self.logger.info(f"Cached {len(votes)} votes for {mp.get('name', mp_slug)} ({i+1}/{len(mps_to_process)})")
                    except Exception as e:
                        self.logger.error(f"Error saving MP votes for {mp_slug}: {e}")
                
                # Small delay between MPs
                time.sleep(0.1)
        
        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        self.log_operation("MP Voting Records", "COMPLETED", f"{successful_updates}/{len(mps_to_process)} MPs updated")
        return successful_updates > 0
    
    def _is_mp_votes_cache_fresh(self, mp_slug: str) -> bool:
        """Check if MP votes cache is still fresh"""
        mp_cache_file = os.path.join(MP_VOTES_CACHE_DIR, f'{mp_slug}.json')
        return not self.is_cache_expired(mp_cache_file, 'mp_votes')
    
    def _build_mp_votes_from_cache(self, mp_slug: str, temp_dir: str) -> List[dict]:
        """Build MP votes from cached vote details (memory efficient)"""
        mp_politician_url = f'/politicians/{mp_slug}/'
        votes_with_ballots = []
        
        # Process vote cache in batches
        vote_files = [f for f in os.listdir(VOTE_DETAILS_CACHE_DIR) if f.endswith('.json')]
        
        batch_size = 50
        for i in range(0, len(vote_files), batch_size):
            batch_files = vote_files[i:i + batch_size]
            
            for vote_file in batch_files:
                try:
                    with open(os.path.join(VOTE_DETAILS_CACHE_DIR, vote_file), 'r') as f:
                        vote_data = json.load(f)
                    
                    vote_info = vote_data.get('vote', {})
                    ballots = vote_data.get('ballots', [])
                    
                    # Find this MP's ballot
                    mp_ballot = None
                    for ballot in ballots:
                        if ballot.get('politician_url') == mp_politician_url:
                            mp_ballot = ballot.get('ballot')
                            break
                    
                    if mp_ballot:
                        vote_with_ballot = vote_info.copy()
                        vote_with_ballot['mp_ballot'] = mp_ballot
                        votes_with_ballots.append(vote_with_ballot)
                        
                except Exception as e:
                    continue
        
        # Sort by date descending
        votes_with_ballots.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return votes_with_ballots[:1000]  # Limit to most recent 1000 votes
    
    def update_historical_mps(self) -> bool:
        """Update historical MPs cache for previous sessions"""
        self.log_operation("Historical MPs", "STARTED")
        
        if not self.is_cache_expired(HISTORICAL_MPS_CACHE_FILE, 'historical_mps'):
            self.log_operation("Historical MPs", "SKIPPED", "Cache still fresh")
            return True
        
        # Get sample votes from session 44-1 to find historical MPs
        historical_votes = self.api_request(f'{PARLIAMENT_API_BASE}/votes/', {
            'limit': 100, 'offset': 0
        })
        
        if not historical_votes or not historical_votes.get('objects'):
            self.log_operation("Historical MPs", "FAILED", "No votes data")
            return False
        
        # Extract unique historical MP URLs from vote ballots
        historical_mp_urls = set()
        
        for vote in historical_votes['objects']:
            if vote.get('session') == '44-1':  # Focus on previous session
                ballots_data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/ballots/', {
                    'vote': vote['url'],
                    'limit': 400
                })
                
                if ballots_data and ballots_data.get('objects'):
                    for ballot in ballots_data['objects']:
                        politician_url = ballot.get('politician_url')
                        if politician_url:
                            historical_mp_urls.add(politician_url)
        
        # Fetch details for historical MPs
        historical_mps = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {}
            
            for mp_url in list(historical_mp_urls)[:200]:  # Limit to 200 MPs
                future = executor.submit(self._fetch_historical_mp, mp_url)
                future_to_url[future] = mp_url
            
            for future in as_completed(future_to_url):
                mp_url = future_to_url[future]
                try:
                    mp_data = future.result(timeout=30)
                    if mp_data:
                        historical_mps.append(mp_data)
                except Exception as e:
                    self.logger.error(f"Error fetching historical MP {mp_url}: {e}")
        
        if historical_mps:
            success = self.save_cache_data(historical_mps, HISTORICAL_MPS_CACHE_FILE, 'historical_mps')
            self.log_operation("Historical MPs", "COMPLETED" if success else "FAILED", 
                             f"{len(historical_mps)} historical MPs")
            return success
        
        self.log_operation("Historical MPs", "FAILED", "No historical MPs found")
        return False
    
    def _fetch_historical_mp(self, mp_url: str) -> Optional[dict]:
        """Fetch details for a single historical MP"""
        return self.api_request(f"{PARLIAMENT_API_BASE}{mp_url}")
    
    def save_statistics(self):
        """Save comprehensive cache statistics"""
        self.stats['end_time'] = datetime.now()
        self.stats['duration_seconds'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        # Add cache file sizes
        for cache_type, file_path in [
            ('politicians', POLITICIANS_CACHE_FILE),
            ('votes', VOTES_CACHE_FILE),
            ('bills', BILLS_CACHE_FILE),
            ('historical_mps', HISTORICAL_MPS_CACHE_FILE)
        ]:
            if os.path.exists(file_path):
                self.stats['cache_sizes'][cache_type] = os.path.getsize(file_path)
        
        # Count vote details and MP votes files
        if os.path.exists(VOTE_DETAILS_CACHE_DIR):
            vote_details_count = len([f for f in os.listdir(VOTE_DETAILS_CACHE_DIR) if f.endswith('.json')])
            self.stats['vote_details_count'] = vote_details_count
        
        if os.path.exists(MP_VOTES_CACHE_DIR):
            mp_votes_count = len([f for f in os.listdir(MP_VOTES_CACHE_DIR) if f.endswith('.json')])
            self.stats['mp_votes_count'] = mp_votes_count
        
        try:
            with open(STATISTICS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2, default=str)
            self.logger.info(f"Cache update completed in {self.stats['duration_seconds']:.1f}s")
            self.logger.info(f"Total API calls: {self.stats['api_calls']}")
            self.logger.info(f"Errors: {len(self.stats['errors'])}")
        except Exception as e:
            self.logger.error(f"Error saving statistics: {e}")
    
    def run_auto_mode(self, max_mps=None):
        """Run automatic cache updates based on expiration"""
        self.logger.info("Starting unified cache update (AUTO mode)")
        
        # Update in optimal order (dependencies first)
        self.update_politicians_cache()
        self.update_votes_cache()
        self.update_vote_details_incremental()
        self.update_bills_cache()
        self.update_mp_voting_records(max_mps=max_mps)
        self.update_historical_mps()
        
        self.save_statistics()
    
    def run_incremental_mode(self, max_mps=None):
        """Run incremental updates only"""
        self.logger.info("Starting unified cache update (INCREMENTAL mode)")
        
        self.update_vote_details_incremental()
        # In incremental mode, only update fresh MP records if cache is expired
        # This will still process all MPs, but only those with expired cache
        self.update_mp_voting_records(max_mps=max_mps)
        
        self.save_statistics()
    
    def run_full_mode(self, max_mps=None):
        """Run full cache rebuild"""
        self.logger.info("Starting unified cache update (FULL mode)")
        
        # Force all updates
        self.force_full = True
        self.run_auto_mode(max_mps=max_mps)

def main():
    parser = argparse.ArgumentParser(description='Unified Cache Update Script')
    parser.add_argument('--mode', choices=['auto', 'incremental', 'full'], default='auto',
                       help='Update mode: auto (smart), incremental (new data only), full (rebuild all)')
    parser.add_argument('--force', action='store_true',
                       help='Force update even if cache is fresh')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO',
                       help='Logging level')
    parser.add_argument('--max-mps', type=int, default=None,
                       help='Maximum number of MPs to cache voting records for (default: all current MPs)')
    
    args = parser.parse_args()
    
    updater = UnifiedCacheUpdater(
        mode=args.mode,
        force_full=args.force,
        log_level=args.log_level
    )
    
    try:
        if args.mode == 'auto':
            updater.run_auto_mode(max_mps=args.max_mps)
        elif args.mode == 'incremental':
            updater.run_incremental_mode(max_mps=args.max_mps)
        elif args.mode == 'full':
            updater.run_full_mode(max_mps=args.max_mps)
            
    except KeyboardInterrupt:
        updater.logger.info("Cache update interrupted by user")
    except Exception as e:
        updater.logger.error(f"Cache update failed: {e}")
        raise

if __name__ == "__main__":
    main()
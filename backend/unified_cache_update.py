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
import sys
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional, Tuple
import argparse
import logging
import urllib.parse
from pathlib import Path

# Configuration
PARLIAMENT_API_BASE = 'https://api.openparliament.ca'
HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'MP-Monitor-Unified-Cache/2.0 (amranu@gmail.com)',
    'API-Version': 'v1'
}

# Cache configuration
CACHE_DIR = '/home/root/mp-monitor/backend/cache'
CACHE_DURATIONS = {
    'politicians': 172800,    # 48 hours - MPs don't change often
    'votes': 172800,         # 48 hours - votes happen frequently but cache longer
    'bills': 172800,         # 48 hours - bills change less frequently
    'vote_details': 172800,  # 48 hours - vote details are immutable
    'mp_votes': 172800,      # 48 hours - MP voting records
    'historical_mps': 604800, # 1 week - historical data changes rarely
    'legisinfo': 172800,     # 48 hours - LEGISinfo data is mostly static
    'images': 2592000,       # 30 days - MP images change rarely
    'debates': 604800,       # 1 week - debates are historical records
    'mp_debates': 172800     # 48 hours - MP-specific debate participation
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
LEGISINFO_CACHE_DIR = os.path.join(CACHE_DIR, 'legisinfo')
IMAGES_CACHE_DIR = os.path.join(CACHE_DIR, 'images')
DEBATES_CACHE_FILE = os.path.join(CACHE_DIR, 'debates.json')
MP_DEBATES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_debates')
STATISTICS_FILE = os.path.join(CACHE_DIR, 'unified_cache_statistics.json')

# API rate limiting
API_DELAY_BETWEEN_REQUESTS = 0.2  # 200ms delay between requests
API_DELAY_BETWEEN_BATCHES = 1.0   # 1 second delay between batches
MAX_CONCURRENT_WORKERS = 3        # Max concurrent API requests

# Process locking
LOCK_FILE = os.path.join(CACHE_DIR, 'unified_cache_update.lock')

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
        self.acquire_lock()
        
    def ensure_cache_dirs(self):
        """Ensure all cache directories exist"""
        os.makedirs(CACHE_DIR, exist_ok=True)
        os.makedirs(MP_VOTES_CACHE_DIR, exist_ok=True)
        os.makedirs(VOTE_DETAILS_CACHE_DIR, exist_ok=True)
        os.makedirs(LEGISINFO_CACHE_DIR, exist_ok=True)
        os.makedirs(IMAGES_CACHE_DIR, exist_ok=True)
        os.makedirs(MP_DEBATES_CACHE_DIR, exist_ok=True)
    
    def acquire_lock(self):
        """Acquire process lock to prevent multiple instances"""
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    lock_data = json.load(f)
                
                # Check if the process is still running
                lock_pid = lock_data.get('pid')
                if lock_pid:
                    try:
                        os.kill(lock_pid, 0)  # Check if process exists
                        self.logger.error(f"Another unified cache update is already running (PID: {lock_pid})")
                        self.logger.error("If you're sure no other process is running, delete the lock file:")
                        self.logger.error(f"rm {LOCK_FILE}")
                        sys.exit(1)
                    except OSError:
                        # Process doesn't exist, remove stale lock
                        self.logger.warning("Removing stale lock file")
                        os.remove(LOCK_FILE)
            except Exception as e:
                self.logger.warning(f"Error reading lock file: {e}, removing it")
                os.remove(LOCK_FILE)
        
        # Create lock file
        lock_data = {
            'pid': os.getpid(),
            'started_at': datetime.now().isoformat(),
            'mode': self.mode
        }
        
        try:
            with open(LOCK_FILE, 'w') as f:
                json.dump(lock_data, f, indent=2)
            self.logger.info(f"Acquired process lock (PID: {os.getpid()})")
        except Exception as e:
            self.logger.error(f"Could not create lock file: {e}")
            sys.exit(1)
    
    def release_lock(self):
        """Release process lock"""
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
                self.logger.info("Released process lock")
        except Exception as e:
            self.logger.error(f"Error releasing lock: {e}")
    
    def __del__(self):
        """Cleanup lock on object destruction"""
        self.release_lock()
        
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
            
        # For image files, check file modification time instead of JSON content
        if cache_type == 'images' or cache_file.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            try:
                file_age = time.time() - os.path.getmtime(cache_file)
                return file_age > CACHE_DURATIONS.get(cache_type, CACHE_DURATIONS['images'])
            except OSError:
                return True
        
        # For JSON cache files, check expires field
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            expires = data.get('expires', 0)
            # Ensure expires is a number (handle different timestamp formats)
            if isinstance(expires, str):
                try:
                    # Try parsing as ISO timestamp first
                    from datetime import datetime
                    expires = datetime.fromisoformat(expires.replace('Z', '+00:00')).timestamp()
                except ValueError:
                    # Fall back to float conversion
                    expires = float(expires)
            return time.time() > expires
            
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
            # If we can't read the file as JSON, fall back to file modification time
            try:
                file_age = time.time() - os.path.getmtime(cache_file)
                return file_age > CACHE_DURATIONS.get(cache_type, 3600)  # Default 1 hour
            except OSError:
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
    
    def clean_debate_content(self, html_content: str) -> dict:
        """
        Clean HTML content from debates and extract metadata
        
        Args:
            html_content: Raw HTML content from OpenParliament API
            
        Returns:
            dict with 'clean_text' and 'metadata' keys
        """
        import re
        
        if not html_content:
            return {'clean_text': '', 'metadata': {}}
        
        metadata = {}
        
        # Extract data-HoCid attribute
        hocid_match = re.search(r'data-HoCid="([^"]*)"', html_content)
        if hocid_match:
            metadata['hoc_id'] = hocid_match.group(1)
        
        # Extract data-originallang attribute
        lang_match = re.search(r'data-originallang="([^"]*)"', html_content)
        if lang_match:
            metadata['original_language'] = lang_match.group(1)
        
        # Extract any other data-* attributes
        data_attrs = re.findall(r'data-([^=]+)="([^"]*)"', html_content)
        for attr_name, attr_value in data_attrs:
            if attr_name not in ['HoCid', 'originallang']:  # Don't duplicate
                metadata[f'data_{attr_name}'] = attr_value
        
        # Clean HTML tags and attributes
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # Replace common HTML entities
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&quot;', '"')
        clean_text = clean_text.replace('&#39;', "'")
        
        # Clean up extra whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = clean_text.strip()
        
        return {
            'clean_text': clean_text,
            'metadata': metadata
        }
    
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
    
    def check_for_new_votes(self) -> bool:
        """Check if there are new votes since last cache update and handle them incrementally"""
        self.logger.info("Checking for new votes to determine if incremental updates are needed...")
        
        try:
            # Get more recent votes from API to catch any new votes
            data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/', {
                'limit': 50, 'offset': 0, 'order_by': '-date'  # Check more votes to be thorough
            })
            
            if not data or not data.get('objects'):
                self.logger.warning("Could not fetch recent votes from API")
                return False
                
            api_votes = data['objects']
            self.logger.info(f"Fetched {len(api_votes)} recent votes from API")
            
            # Get vote IDs and full vote objects from API
            api_vote_data = {}
            for vote in api_votes:
                vote_url = vote.get('url', '')
                if vote_url:
                    # Extract vote ID from URL (e.g., /votes/44-1/451/ -> 44-1_451)
                    vote_id = vote_url.replace('/votes/', '').replace('/', '_').rstrip('_')
                    if vote_id:
                        api_vote_data[vote_id] = vote
                        self.logger.debug(f"API vote ID: {vote_id}, Date: {vote.get('date')}")
            
            if not api_vote_data:
                self.logger.warning("No valid vote IDs found in API response")
                return False
            
            # Check cached votes
            cached_vote_ids = set()
            if os.path.exists(VOTES_CACHE_FILE):
                try:
                    with open(VOTES_CACHE_FILE, 'r') as f:
                        cached_votes_data = json.load(f)
                    
                    # Handle both old format (direct list) and new format (with data wrapper)
                    cached_votes = cached_votes_data.get('data', cached_votes_data) if isinstance(cached_votes_data, dict) else cached_votes_data
                    
                    if cached_votes:
                        for vote in cached_votes:
                            # Handle both dict and string objects
                            if isinstance(vote, dict):
                                vote_url = vote.get('url', '')
                                if vote_url:
                                    # Extract vote ID from URL
                                    vote_id = vote_url.replace('/votes/', '').replace('/', '_').rstrip('_')
                                    if vote_id:
                                        cached_vote_ids.add(vote_id)
                                        self.logger.debug(f"Cached vote ID: {vote_id}, Date: {vote.get('date')}")
                            else:
                                self.logger.warning(f"Unexpected vote format in cache: {type(vote)}")
                except Exception as e:
                    self.logger.warning(f"Error reading cached votes: {e}")
            
            # Check if there are any new vote IDs in API that aren't in cache
            new_vote_ids = set(api_vote_data.keys()) - cached_vote_ids
            
            # Also check for newer votes by date if we have cached data
            if not new_vote_ids and cached_votes and api_votes:
                # Get the most recent cached vote date
                try:
                    cached_dates = []
                    for vote in cached_votes[:10]:  # Check recent cached votes
                        if isinstance(vote, dict) and vote.get('date'):
                            cached_dates.append(vote['date'])
                    
                    if cached_dates:
                        most_recent_cached = max(cached_dates)
                        self.logger.info(f"Most recent cached vote date: {most_recent_cached}")
                        
                        # Check if API has votes newer than our most recent cached vote
                        for vote_id, vote_data in api_vote_data.items():
                            vote_date = vote_data.get('date', '')
                            if vote_date and vote_date > most_recent_cached:
                                self.logger.info(f"Found newer vote by date: {vote_id} ({vote_date} > {most_recent_cached})")
                                new_vote_ids.add(vote_id)
                except Exception as e:
                    self.logger.warning(f"Error in date-based new vote detection: {e}")
            
            if new_vote_ids:
                self.logger.info(f"New votes detected! Found {len(new_vote_ids)} new vote(s): {', '.join(sorted(new_vote_ids))}")
                
                # Process new votes incrementally instead of expiring all caches
                success = self._process_new_votes_incrementally(new_vote_ids, api_vote_data)
                
                if success:
                    self.logger.info("Successfully processed new votes incrementally")
                    
                    # Immediately update party line stats with new votes
                    self.logger.info("Updating party-line stats with new votes...")
                    party_line_success = self.update_party_line_stats_force()
                    if party_line_success:
                        self.logger.info("Party-line stats updated successfully with new votes")
                    else:
                        self.logger.warning("Failed to update party-line stats with new votes")
                    
                    return True
                else:
                    self.logger.warning("Incremental processing failed, falling back to full cache expiration")
                    # Fallback to old behavior if incremental processing fails
                    fallback_success = self._expire_all_vote_caches(new_vote_ids)
                    if fallback_success:
                        # Also try to update party-line stats immediately in fallback case
                        self.logger.info("Attempting party-line stats update after fallback...")
                        party_line_success = self.update_party_line_stats_force()
                        if party_line_success:
                            self.logger.info("Party-line stats updated successfully after fallback")
                        else:
                            self.logger.warning("Failed to update party-line stats after fallback")
                    return fallback_success
            else:
                self.logger.info(f"No new votes found. API has {len(api_vote_data)} votes, all present in cache")
                
        except Exception as e:
            self.logger.error(f"Error checking for new votes: {e}")
            
        return False
    
    def _process_new_votes_incrementally(self, new_vote_ids: set, api_vote_data: dict) -> bool:
        """Process new votes incrementally by adding them to existing caches"""
        try:
            self.logger.info(f"Processing {len(new_vote_ids)} new votes incrementally...")
            
            # 1. Add new votes to the main votes cache
            if not self._add_votes_to_cache(new_vote_ids, api_vote_data):
                return False
            
            # 2. Cache vote details for new votes
            if not self._cache_new_vote_details(new_vote_ids, api_vote_data):
                return False
            
            # 3. Update MP voting records with new votes
            if not self._update_mp_records_with_new_votes(new_vote_ids):
                return False
            
            # 4. Update bills cache if any new votes are related to bills
            self._update_bills_cache_for_new_votes(new_vote_ids, api_vote_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in incremental vote processing: {e}")
            return False
    
    def _add_votes_to_cache(self, new_vote_ids: set, api_vote_data: dict) -> bool:
        """Add new votes to the main votes cache file"""
        try:
            # Load existing votes cache
            existing_votes = []
            if os.path.exists(VOTES_CACHE_FILE):
                with open(VOTES_CACHE_FILE, 'r') as f:
                    cached_data = json.load(f)
                existing_votes = cached_data.get('data', cached_data) if isinstance(cached_data, dict) else cached_data
            
            # Add new votes to the beginning (most recent first)
            new_votes = [api_vote_data[vote_id] for vote_id in new_vote_ids]
            updated_votes = new_votes + existing_votes
            
            # Limit total votes to prevent cache from growing too large
            max_votes = 200
            if len(updated_votes) > max_votes:
                updated_votes = updated_votes[:max_votes]
                self.logger.info(f"Trimmed votes cache to {max_votes} most recent votes")
            
            # Save updated votes cache
            return self.save_cache_data(updated_votes, VOTES_CACHE_FILE, 'votes')
            
        except Exception as e:
            self.logger.error(f"Error adding votes to cache: {e}")
            return False
    
    def _cache_new_vote_details(self, new_vote_ids: set, api_vote_data: dict) -> bool:
        """Cache detailed information for new votes"""
        try:
            successful_caches = 0
            
            for vote_id in new_vote_ids:
                vote = api_vote_data[vote_id]
                
                # Cache the vote details
                if self._cache_single_vote_details(vote_id, vote):
                    successful_caches += 1
                    
                    # Update vote cache index
                    self._update_vote_cache_index(vote_id, vote)
                    
                    # Small delay to be respectful to API
                    time.sleep(0.2)
            
            self.logger.info(f"Successfully cached details for {successful_caches}/{len(new_vote_ids)} new votes")
            return successful_caches > 0
            
        except Exception as e:
            self.logger.error(f"Error caching new vote details: {e}")
            return False
    
    def _update_vote_cache_index(self, vote_id: str, vote: dict):
        """Update the vote cache index with new vote"""
        try:
            index_data = {}
            if os.path.exists(VOTE_CACHE_INDEX_FILE):
                with open(VOTE_CACHE_INDEX_FILE, 'r') as f:
                    index_data = json.load(f)
            
            if 'cached_votes' not in index_data:
                index_data['cached_votes'] = {}
            
            index_data['cached_votes'][vote_id] = {
                'url': vote['url'],
                'date': vote.get('date'),
                'cached_at': datetime.now().isoformat()
            }
            
            index_data['updated'] = datetime.now().isoformat()
            index_data['total_cached'] = len(index_data['cached_votes'])
            
            with open(VOTE_CACHE_INDEX_FILE, 'w') as f:
                json.dump(index_data, f, indent=2)
                
        except Exception as e:
            self.logger.warning(f"Error updating vote cache index: {e}")
    
    def _update_mp_records_with_new_votes(self, new_vote_ids: set) -> bool:
        """Update MP voting records by adding new votes incrementally"""
        try:
            if not os.path.exists(MP_VOTES_CACHE_DIR):
                return True  # No existing MP records to update
            
            updated_count = 0
            mp_files = [f for f in os.listdir(MP_VOTES_CACHE_DIR) if f.endswith('.json')]
            
            self.logger.info(f"Updating {len(mp_files)} MP voting records with new votes...")
            
            for mp_file in mp_files:
                mp_slug = mp_file.replace('.json', '')
                mp_cache_path = os.path.join(MP_VOTES_CACHE_DIR, mp_file)
                
                try:
                    # Load existing MP votes
                    with open(mp_cache_path, 'r') as f:
                        mp_data = json.load(f)
                    
                    existing_votes = mp_data.get('data', [])
                    mp_url = f'/politicians/{mp_slug}/'
                    
                    # Find new votes where this MP participated
                    new_mp_votes = []
                    for vote_id in new_vote_ids:
                        vote_details_file = os.path.join(VOTE_DETAILS_CACHE_DIR, f'{vote_id}.json')
                        if os.path.exists(vote_details_file):
                            with open(vote_details_file, 'r') as f:
                                vote_data = json.load(f)
                            
                            vote_info = vote_data.get('vote', {})
                            ballots = vote_data.get('ballots', [])
                            
                            # Find this MP's ballot
                            for ballot in ballots:
                                if ballot.get('politician_url') == mp_url:
                                    vote_record = vote_info.copy()
                                    vote_record['mp_ballot'] = ballot.get('ballot')
                                    new_mp_votes.append(vote_record)
                                    break
                    
                    if new_mp_votes:
                        # Add new votes to the beginning (most recent first)
                        updated_votes = new_mp_votes + existing_votes
                        
                        # Limit to prevent excessive growth
                        max_votes = 5000
                        if len(updated_votes) > max_votes:
                            updated_votes = updated_votes[:max_votes]
                        
                        # Save updated MP votes
                        mp_data['data'] = updated_votes
                        mp_data['updated'] = datetime.now().isoformat()
                        mp_data['count'] = len(updated_votes)
                        
                        with open(mp_cache_path, 'w') as f:
                            json.dump(mp_data, f, indent=2)
                        
                        updated_count += 1
                        self.logger.debug(f"Added {len(new_mp_votes)} new votes for MP: {mp_slug}")
                
                except Exception as e:
                    self.logger.warning(f"Error updating MP votes for {mp_slug}: {e}")
                    continue
            
            self.logger.info(f"Successfully updated {updated_count} MP voting records with new votes")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating MP records with new votes: {e}")
            return False
    
    def _update_bills_cache_for_new_votes(self, new_vote_ids: set, api_vote_data: dict):
        """Update bills cache index if any new votes are related to bills"""
        try:
            # Check if any new votes are related to bills
            bills_affected = False
            for vote_id in new_vote_ids:
                vote = api_vote_data[vote_id]
                if vote.get('bill_url'):
                    bills_affected = True
                    break
            
            if bills_affected:
                self.logger.info("New votes affect bills, updating bills with votes index...")
                self._build_bills_with_votes_index()
            
        except Exception as e:
            self.logger.warning(f"Error updating bills cache for new votes: {e}")
    
    def _expire_all_vote_caches(self, new_vote_ids: set) -> bool:
        """Fallback method: expire all vote-related caches (original behavior)"""
        self.logger.info("Using fallback: expiring all vote-related caches...")
        
        # Expire vote-related caches by modifying their timestamps
        self._expire_cache_file(VOTES_CACHE_FILE)
        self._expire_cache_file(BILLS_CACHE_FILE)  # Bills might have new votes
        
        # Expire MP votes caches (they contain vote data)
        if os.path.exists(MP_VOTES_CACHE_DIR):
            expired_count = 0
            for mp_file in os.listdir(MP_VOTES_CACHE_DIR):
                if mp_file.endswith('.json'):
                    mp_cache_path = os.path.join(MP_VOTES_CACHE_DIR, mp_file)
                    self._expire_cache_file(mp_cache_path)
                    expired_count += 1
            self.logger.info(f"Expired {expired_count} MP voting record caches")
        
        # Expire party line stats (they depend on vote data)
        party_line_cache = os.path.join(CACHE_DIR, 'party_line_stats.json')
        if os.path.exists(party_line_cache):
            self._expire_cache_file(party_line_cache)
        
        return True
    
    def _expire_cache_file(self, cache_file: str):
        """Expire a cache file by updating its expires timestamp in JSON content"""
        try:
            if os.path.exists(cache_file):
                # For JSON cache files, update the expires field
                if cache_file.endswith('.json'):
                    try:
                        with open(cache_file, 'r') as f:
                            data = json.load(f)
                        
                        # Set expires to a time in the past
                        data['expires'] = time.time() - 3600  # 1 hour ago
                        
                        with open(cache_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        self.logger.info(f"Expired cache file: {os.path.basename(cache_file)}")
                        return
                    except (json.JSONDecodeError, KeyError):
                        # If JSON parsing fails, fall back to modification time
                        pass
                
                # For non-JSON files (like images), set modification time to old date
                old_time = time.time() - (7 * 24 * 60 * 60)
                os.utime(cache_file, (old_time, old_time))
                self.logger.info(f"Expired cache file: {os.path.basename(cache_file)}")
        except Exception as e:
            self.logger.warning(f"Could not expire cache file {cache_file}: {e}")
    
    def update_votes_cache(self) -> bool:
        """Update recent votes cache"""
        self.log_operation("Votes Cache", "STARTED")
        
        if not self.is_cache_expired(VOTES_CACHE_FILE, 'votes'):
            self.log_operation("Votes Cache", "SKIPPED", "Cache still fresh")
            return True
            
        data = self.api_request(f'{PARLIAMENT_API_BASE}/votes/', {
            'limit': 100, 'offset': 0, 'order_by': '-date'
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
            # Enrich bills with sponsor information
            enriched_bills = self._enrich_bills_with_sponsors(all_bills)
            
            success = self.save_cache_data(enriched_bills, BILLS_CACHE_FILE, 'bills')
            if success:
                self._build_bills_with_votes_index()
            
            sponsor_count = len([bill for bill in enriched_bills if bill.get('sponsor_politician_url')])
            self.log_operation("Bills Cache", "COMPLETED" if success else "FAILED", 
                             f"{len(enriched_bills)} bills, {sponsor_count} with sponsors")
            return success
        
        self.log_operation("Bills Cache", "FAILED", "No data retrieved")
        return False
    
    def _enrich_bills_with_sponsors(self, bills: List[dict]) -> List[dict]:
        """Enrich bills with sponsor information from LEGISinfo"""
        try:
            # Load politicians for sponsor mapping
            try:
                with open(POLITICIANS_CACHE_FILE, 'r') as f:
                    politicians_data = json.load(f)
                politicians = politicians_data.get('data', [])
            except Exception as e:
                self.logger.warning(f"Could not load politicians for sponsor mapping: {e}")
                return bills
            
            # Create name to URL mapping
            politician_name_to_url = {}
            for mp in politicians:
                if mp.get('name'):
                    name = mp['name'].strip()
                    politician_name_to_url[name] = mp['url']
                    
                    # Also store first-last format
                    name_parts = name.split()
                    if len(name_parts) >= 2:
                        first_last = f"{name_parts[0]} {name_parts[-1]}"
                        if first_last != name:
                            politician_name_to_url[first_last] = mp['url']
            
            enriched_bills = []
            enrichment_count = 0
            
            # Target recent sessions for enrichment (match Flask backend)
            target_sessions = ['45-1', '44-1', '43-2', '43-1', '42-1', '41-2', '41-1']
            
            for bill in bills:
                enriched_bill = bill.copy()
                
                # Only enrich bills from target sessions to save time
                if bill.get('session') not in target_sessions:
                    enriched_bills.append(enriched_bill)
                    continue
                
                # Fetch sponsor info from LEGISinfo
                sponsor_info = self._fetch_legisinfo_sponsor(bill.get('session', ''), bill.get('number', ''))
                
                if sponsor_info:
                    sponsor_name = sponsor_info.strip()
                    
                    # Try exact match first
                    sponsor_url = politician_name_to_url.get(sponsor_name)
                    
                    # If no exact match, try partial matching
                    if not sponsor_url:
                        for name, url in politician_name_to_url.items():
                            if (name.lower() in sponsor_name.lower() or 
                                sponsor_name.lower() in name.lower()):
                                sponsor_url = url
                                break
                    
                    if sponsor_url:
                        enriched_bill['sponsor_politician_url'] = sponsor_url
                        enriched_bill['sponsor_name'] = sponsor_name
                        enrichment_count += 1
                        self.logger.info(f"Matched sponsor {sponsor_name} -> {sponsor_url} for {bill.get('session')}/{bill.get('number')}")
                    else:
                        self.logger.debug(f"Could not match sponsor '{sponsor_name}' for {bill.get('session')}/{bill.get('number')}")
                
                enriched_bills.append(enriched_bill)
                
                # Small delay to avoid overwhelming LEGISinfo API
                time.sleep(0.1)
            
            self.logger.info(f"Enriched {enrichment_count}/{len(bills)} bills with sponsor information")
            return enriched_bills
            
        except Exception as e:
            self.logger.error(f"Error enriching bills with sponsors: {e}")
            return bills
    
    def _fetch_legisinfo_sponsor(self, session: str, bill_number: str) -> Optional[str]:
        """Fetch sponsor name from LEGISinfo API with caching"""
        try:
            # Create safe filename
            safe_bill_number = bill_number.replace('/', '_').replace('\\', '_')
            cache_filename = f"{session}_{safe_bill_number}.json"
            cache_file_path = os.path.join(LEGISINFO_CACHE_DIR, cache_filename)
            
            # Ensure cache directory exists
            os.makedirs(LEGISINFO_CACHE_DIR, exist_ok=True)
            
            # Check if cache exists and is fresh
            if os.path.exists(cache_file_path):
                try:
                    cache_mtime = os.path.getmtime(cache_file_path)
                    if time.time() - cache_mtime < CACHE_DURATIONS['legisinfo']:
                        with open(cache_file_path, 'r') as f:
                            cached_data = json.load(f)
                        return cached_data.get('SponsorPersonName')
                except Exception as e:
                    self.logger.debug(f"Error reading LEGISinfo cache for {session}/{bill_number}: {e}")
            
            # Fetch from API
            url = f"https://www.parl.ca/LegisInfo/en/bill/{session}/{bill_number.lower()}/json"
            response = requests.get(url, timeout=10)
            
            if not response.ok:
                return None
            
            data = response.json()
            if not data:
                return None
            
            # Handle both list and dict responses
            if isinstance(data, list) and len(data) > 0:
                legis_info = data[0]
            elif isinstance(data, dict):
                legis_info = data
            else:
                return None
            
            # Cache the data
            try:
                with open(cache_file_path, 'w') as f:
                    json.dump(legis_info, f, indent=2)
                self.logger.debug(f"Cached LEGISinfo data for {session}/{bill_number}")
            except Exception as e:
                self.logger.debug(f"Error caching LEGISinfo data for {session}/{bill_number}: {e}")
            
            return legis_info.get('SponsorPersonName')
            
        except Exception as e:
            self.logger.debug(f"Error fetching LEGISinfo data for {session}/{bill_number}: {e}")
            return None
    
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
        seen_vote_urls = set()  # Track processed votes to avoid duplicates
        
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
                    
                    # Skip if we've already processed this vote (prevents duplicates from different file naming)
                    vote_url = vote_info.get('url', '')
                    if vote_url in seen_vote_urls:
                        continue
                    seen_vote_urls.add(vote_url)
                    
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
        
        return votes_with_ballots[:5000]  # Limit to most recent 5000 votes
    
    def update_historical_mps(self) -> bool:
        """Update historical MPs cache from cached vote details"""
        self.log_operation("Historical MPs", "STARTED")
        
        if not self.is_cache_expired(HISTORICAL_MPS_CACHE_FILE, 'historical_mps'):
            self.log_operation("Historical MPs", "SKIPPED", "Cache still fresh")
            return True
        
        # Extract unique historical MP URLs from cached vote details (more comprehensive)
        historical_mp_urls = set()
        
        # Process all cached vote details to find historical MPs
        vote_cache_files = []
        if os.path.exists(VOTE_DETAILS_CACHE_DIR):
            vote_cache_files = [f for f in os.listdir(VOTE_DETAILS_CACHE_DIR) if f.endswith('.json')]
        
        for vote_file in vote_cache_files:
            try:
                vote_path = os.path.join(VOTE_DETAILS_CACHE_DIR, vote_file)
                with open(vote_path, 'r') as f:
                    vote_data = json.load(f)
                
                # Focus on historical sessions (not current session 45-1)
                vote_info = vote_data.get('vote', {})
                session = vote_info.get('session', '')
                
                if session and session != '45-1':  # Include all historical sessions
                    ballots = vote_data.get('ballots', [])
                    for ballot in ballots:
                        politician_url = ballot.get('politician_url')
                        if politician_url:
                            historical_mp_urls.add(politician_url)
                            
            except Exception as e:
                self.logger.debug(f"Error processing vote file {vote_file}: {e}")
                continue
        
        self.logger.info(f"Found {len(historical_mp_urls)} unique historical MP URLs")
        
        # Fetch details for historical MPs (increase limit for comprehensive coverage)
        historical_mps = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {}
            
            # Process all historical MPs found in vote cache
            for mp_url in list(historical_mp_urls):
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
    
    def update_debates_cache(self) -> bool:
        """Update debates cache with recent parliamentary debates"""
        self.log_operation("Debates Cache", "STARTED")
        
        if not self.is_cache_expired(DEBATES_CACHE_FILE, 'debates'):
            self.log_operation("Debates Cache", "SKIPPED", "Cache still fresh")
            return True
        
        # Fetch recent debates from OpenParliament API
        all_debates = []
        offset = 0
        limit = 50
        max_debates = 1000  # Limit to most recent 1000 debates for performance
        
        while len(all_debates) < max_debates:
            data = self.api_request(f'{PARLIAMENT_API_BASE}/debates/', {
                'limit': limit, 'offset': offset
            })
            
            if not data or not data.get('objects'):
                break
                
            debates = data['objects']
            all_debates.extend(debates)
            self.logger.info(f"Loaded {len(debates)} debates (total: {len(all_debates)})")
            
            # Stop if we have enough or no more data
            if not data.get('pagination', {}).get('next_url') or len(debates) < limit:
                break
                
            offset += limit
            
            # Safety break
            if offset > 2000:
                self.logger.warning("Debates: Safety break at offset 2000")
                break
        
        if all_debates:
            # Sort debates by date (most recent first)
            all_debates.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            # Limit to most recent debates
            all_debates = all_debates[:max_debates]
            
            success = self.save_cache_data(all_debates, DEBATES_CACHE_FILE, 'debates')
            self.log_operation("Debates Cache", "COMPLETED" if success else "FAILED", 
                             f"{len(all_debates)} debates")
            return success
        
        self.log_operation("Debates Cache", "FAILED", "No debates retrieved")
        return False
    
    def update_mp_debates_cache(self, max_mps: int = None) -> bool:
        """Update MP-specific debates cache for current MPs"""
        self.log_operation("MP Debates Cache", "STARTED")
        
        # Load current politicians
        if not os.path.exists(POLITICIANS_CACHE_FILE):
            self.logger.error("Politicians cache not found - run politicians cache first")
            return False
        
        try:
            with open(POLITICIANS_CACHE_FILE, 'r') as f:
                politicians_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading politicians cache: {e}")
            return False
        
        if not politicians_data.get('data'):
            self.logger.error("Politicians cache is not properly cached")
            return False
        
        politicians = politicians_data['data']
        if max_mps:
            politicians = politicians[:max_mps]
        
        self.logger.info(f"Updating debates cache for {len(politicians)} MPs")
        
        successful_updates = 0
        failed_updates = 0
        
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
            future_to_mp = {}
            
            for mp in politicians:
                mp_slug = mp.get('url', '').replace('/politicians/', '').replace('/', '')
                if not mp_slug:
                    continue
                
                # Check if MP debates cache is fresh
                mp_cache_file = os.path.join(MP_DEBATES_CACHE_DIR, f'{mp_slug}.json')
                if not self.is_cache_expired(mp_cache_file, 'mp_debates'):
                    continue
                
                future = executor.submit(self._update_single_mp_debates, mp_slug, mp.get('name', 'Unknown'))
                future_to_mp[future] = (mp_slug, mp.get('name', 'Unknown'))
            
            for future in as_completed(future_to_mp):
                mp_slug, mp_name = future_to_mp[future]
                try:
                    success = future.result(timeout=60)
                    if success:
                        successful_updates += 1
                    else:
                        failed_updates += 1
                except Exception as e:
                    self.logger.error(f"Error updating debates for {mp_name} ({mp_slug}): {e}")
                    failed_updates += 1
        
        self.log_operation("MP Debates Cache", "COMPLETED", 
                         f"{successful_updates} successful, {failed_updates} failed")
        return successful_updates > 0
    
    def _update_single_mp_debates(self, mp_slug: str, mp_name: str) -> bool:
        """Update debates cache for a single MP"""
        try:
            # Fetch MP speeches from OpenParliament API (speeches are part of debates)
            all_speeches = []
            offset = 0
            limit = 50
            max_speeches = 500  # Limit per MP for performance
            
            while len(all_speeches) < max_speeches:
                # Use politician filter in speeches API
                data = self.api_request(f'{PARLIAMENT_API_BASE}/speeches/', {
                    'politician': f'/politicians/{mp_slug}/',
                    'limit': limit,
                    'offset': offset
                })
                
                if not data or not data.get('objects'):
                    break
                
                speeches = data['objects']
                all_speeches.extend(speeches)
                
                # Stop if no more data or we have enough
                if not data.get('pagination', {}).get('next_url') or len(speeches) < limit:
                    break
                
                offset += limit
                
                # Safety break
                if offset > 1000:
                    break
            
            # Group speeches by debate using h1/h2/h3 hierarchy
            debates_participation = []
            debates_seen = set()
            
            for speech in all_speeches:
                # Create debate identifier from h1, h2, h3 fields
                h1 = speech.get('h1', {}).get('en', '') if speech.get('h1') else ''
                h2 = speech.get('h2', {}).get('en', '') if speech.get('h2') else ''
                h3 = speech.get('h3', {}).get('en', '') if speech.get('h3') else ''
                
                # Skip if no debate context
                if not h1 and not h2 and not h3:
                    continue
                
                # Create unique debate identifier
                debate_id = f"{h1}|{h2}|{h3}".strip('|')
                speech_date = speech.get('time', '').split('T')[0] if speech.get('time') else ''
                debate_key = f"{speech_date}:{debate_id}"
                
                if debate_key in debates_seen:
                    continue
                
                debates_seen.add(debate_key)
                
                # Create debate participation record
                raw_content = speech.get('content', {}).get('en', '') if speech.get('content', {}).get('en') else ''
                
                # Clean content and extract metadata
                content_data = self.clean_debate_content(raw_content)
                clean_content = content_data['clean_text']
                content_metadata = content_data['metadata']
                
                debate_info = {
                    'debate_id': debate_id,
                    'debate_title': h3 or h2 or h1 or 'Parliamentary Debate',
                    'debate_category': h1 or 'Parliamentary Business',
                    'debate_subcategory': h2 or '',
                    'debate_topic': h3 or '',
                    'date': speech_date,
                    'content_preview': clean_content[:200] if clean_content else '',
                    'content_full': clean_content,
                    'content_metadata': content_metadata,
                    'speaking_time': len(clean_content) if clean_content else 0,
                    'procedural': speech.get('procedural', False),
                    'speech_url': speech.get('url', '')
                }
                
                debates_participation.append(debate_info)
            
            # Sort by date (most recent first)
            debates_participation.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            # Limit to most recent debates
            debates_participation = debates_participation[:100]
            
            # Save MP debates cache
            mp_debates_data = {
                'mp_slug': mp_slug,
                'mp_name': mp_name,
                'debates_count': len(debates_participation),
                'speeches_analyzed': len(all_speeches),
                'debates': debates_participation,
                'last_updated': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(seconds=CACHE_DURATIONS['mp_debates'])).isoformat()
            }
            
            mp_cache_file = os.path.join(MP_DEBATES_CACHE_DIR, f'{mp_slug}.json')
            
            try:
                with open(mp_cache_file, 'w') as f:
                    json.dump(mp_debates_data, f, indent=2, ensure_ascii=False)
                
                self.logger.debug(f"Cached {len(debates_participation)} debates for {mp_name}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error saving debates cache for {mp_name}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching debates for {mp_name}: {e}")
            return False
    
    def update_mp_images_cache(self) -> bool:
        """Download and cache MP profile images"""
        self.log_operation("MP Images Cache", "STARTED")
        
        # Check if images cache is expired first
        if not self.force_full:
            # Check if any image files exist and if they're fresh
            if os.path.exists(IMAGES_CACHE_DIR):
                image_files = [f for f in os.listdir(IMAGES_CACHE_DIR) if f.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
                if image_files:
                    # Check a sample of image files to see if they're fresh
                    sample_size = min(10, len(image_files))
                    fresh_count = 0
                    for image_file in image_files[:sample_size]:
                        image_path = os.path.join(IMAGES_CACHE_DIR, image_file)
                        if not self.is_cache_expired(image_path, 'images'):
                            fresh_count += 1
                    
                    # If most images are fresh, skip update
                    if fresh_count >= sample_size * 0.8:  # 80% are fresh
                        self.log_operation("MP Images Cache", "SKIPPED", f"Most images still fresh ({fresh_count}/{sample_size} sampled)")
                        return True
        
        # Load politicians list
        try:
            with open(POLITICIANS_CACHE_FILE, 'r') as f:
                politicians_data = json.load(f)
            politicians = politicians_data.get('data', [])
        except Exception as e:
            self.log_operation("MP Images Cache", "FAILED", f"Cannot load politicians: {e}")
            return False
        
        # For auto mode, only cache current MPs to avoid long processing times
        # Historical MPs can be cached separately if needed
        if self.mode == 'auto':
            all_mps = politicians
            self.logger.info(f"Found {len(politicians)} current MPs for image caching (auto mode)")
        else:
            # Also load historical MPs for comprehensive image caching in full mode
            historical_mps = []
            try:
                if os.path.exists(HISTORICAL_MPS_CACHE_FILE):
                    with open(HISTORICAL_MPS_CACHE_FILE, 'r') as f:
                        historical_data = json.load(f)
                    historical_mps = historical_data.get('data', [])
            except Exception as e:
                self.logger.warning(f"Could not load historical MPs for image caching: {e}")
            
            # Combine current and historical MPs
            all_mps = politicians + historical_mps
            self.logger.info(f"Found {len(politicians)} current MPs and {len(historical_mps)} historical MPs for image caching")
        
        successful_downloads = 0
        skipped_existing = 0
        failed_downloads = 0
        
        # Process MPs in batches to avoid overwhelming the server
        batch_size = 10
        for i in range(0, len(all_mps), batch_size):
            batch = all_mps[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_mp = {}
                
                for mp in batch:
                    if mp.get('image'):
                        future = executor.submit(self._download_mp_image, mp)
                        future_to_mp[future] = mp
                
                for future in as_completed(future_to_mp):
                    mp = future_to_mp[future]
                    try:
                        result = future.result(timeout=30)
                        if result == 'downloaded':
                            successful_downloads += 1
                        elif result == 'skipped':
                            skipped_existing += 1
                        else:
                            failed_downloads += 1
                    except Exception as e:
                        failed_downloads += 1
                        self.logger.error(f"Error downloading image for {mp.get('name', 'Unknown')}: {e}")
            
            # Progress logging
            processed = min((i + 1) * batch_size, len(all_mps))
            self.logger.info(f"Processed {processed}/{len(all_mps)} MP images")
            
            # Delay between batches to be respectful
            time.sleep(1.0)
        
        # Cleanup orphaned images (MPs no longer in the system)
        cleanup_count = self._cleanup_orphaned_images(all_mps)
        
        self.log_operation("MP Images Cache", "COMPLETED", 
                         f"{successful_downloads} downloaded, {skipped_existing} skipped, {failed_downloads} failed, {cleanup_count} cleaned up")
        return True
    
    def _download_mp_image(self, mp: dict) -> str:
        """Download image for a single MP"""
        try:
            # Extract MP slug from URL
            mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
            image_url = mp.get('image')
            
            if not image_url:
                return 'no_image'
            
            # Determine file extension from image URL
            parsed_url = urllib.parse.urlparse(image_url)
            path = parsed_url.path.lower()
            
            if path.endswith('.jpg') or path.endswith('.jpeg'):
                ext = 'jpg'
            elif path.endswith('.png'):
                ext = 'png'
            elif path.endswith('.gif'):
                ext = 'gif'
            elif path.endswith('.webp'):
                ext = 'webp'
            else:
                ext = 'jpg'  # Default fallback
            
            image_path = os.path.join(IMAGES_CACHE_DIR, f"{mp_slug}.{ext}")
            
            # Skip if image already exists and is recent (within cache duration)
            if os.path.exists(image_path):
                file_age = time.time() - os.path.getmtime(image_path)
                if file_age < CACHE_DURATIONS['images']:
                    return 'skipped'
            
            # Download image
            full_image_url = f"https://openparliament.ca{image_url}"
            response = requests.get(full_image_url, timeout=15, stream=True)
            response.raise_for_status()
            
            # Save image
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify the image was downloaded correctly
            if os.path.getsize(image_path) > 1024:  # At least 1KB
                self.logger.info(f"Downloaded image for {mp.get('name', mp_slug)} ({os.path.getsize(image_path)} bytes)")
                return 'downloaded'
            else:
                # Remove invalid file
                os.remove(image_path)
                return 'failed'
                
        except Exception as e:
            self.logger.error(f"Error downloading image for {mp.get('name', 'Unknown')}: {e}")
            return 'failed'
    
    def _cleanup_orphaned_images(self, current_mps: List[dict]) -> int:
        """Remove image files for MPs no longer in the system"""
        try:
            # Get list of current MP slugs
            current_slugs = set()
            for mp in current_mps:
                mp_slug = mp['url'].replace('/politicians/', '').replace('/', '')
                current_slugs.add(mp_slug)
            
            # Check existing image files
            cleanup_count = 0
            if os.path.exists(IMAGES_CACHE_DIR):
                for filename in os.listdir(IMAGES_CACHE_DIR):
                    if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        mp_slug = filename.rsplit('.', 1)[0]  # Remove extension
                        if mp_slug not in current_slugs:
                            image_path = os.path.join(IMAGES_CACHE_DIR, filename)
                            try:
                                os.remove(image_path)
                                cleanup_count += 1
                                self.logger.info(f"Cleaned up orphaned image: {filename}")
                            except Exception as e:
                                self.logger.error(f"Error removing orphaned image {filename}: {e}")
            
            return cleanup_count
            
        except Exception as e:
            self.logger.error(f"Error during image cleanup: {e}")
            return 0
    
    def update_party_line_stats(self) -> bool:
        """Update party-line voting statistics after vote cache updates"""
        self.log_operation("Party-Line Stats", "STARTED")
        
        try:
            # Import and call the party-line update function
            import cache_party_line_stats
            
            # Check if party-line cache needs update
            cached_data = cache_party_line_stats.load_party_line_cache()
            if not self.force_full and cached_data:
                # Check if cache is still valid
                try:
                    cache_expires = datetime.fromisoformat(cached_data['summary']['cache_expires'])
                    if datetime.now() < cache_expires:
                        self.log_operation("Party-Line Stats", "SKIPPED", "Cache still fresh")
                        return True
                except:
                    pass  # If we can't parse expiration, proceed with update
            
            # Run party-line calculation with memory limits and increased vote limit
            self.logger.info("Calculating party-line statistics with memory optimization...")
            stats_data = cache_party_line_stats.calculate_all_party_line_stats(max_votes_per_mp=5000)
            
            if stats_data:
                success = cache_party_line_stats.save_party_line_cache(stats_data)
                if success:
                    mp_count = stats_data['summary']['total_mps_analyzed']
                    self.log_operation("Party-Line Stats", "COMPLETED", f"{mp_count} MPs analyzed")
                    return True
                else:
                    self.log_operation("Party-Line Stats", "FAILED", "Could not save cache")
                    return False
            else:
                self.log_operation("Party-Line Stats", "FAILED", "No data calculated")
                return False
                
        except Exception as e:
            self.log_operation("Party-Line Stats", "FAILED", f"Error: {e}")
            self.logger.error(f"Party-line stats update error: {e}")
            return False
    
    def update_party_line_stats_force(self) -> bool:
        """Force update party-line voting statistics regardless of cache expiration"""
        self.log_operation("Party-Line Stats (Forced)", "STARTED")
        
        try:
            # Import and call the party-line update function
            import cache_party_line_stats
            
            # Force recalculation regardless of cache status
            self.logger.info("Force calculating party-line statistics with new votes...")
            stats_data = cache_party_line_stats.calculate_all_party_line_stats(
                max_votes_per_mp=5000, 
                force_recalculate=True
            )
            
            if stats_data:
                success = cache_party_line_stats.save_party_line_cache(stats_data)
                if success:
                    mp_count = stats_data['summary']['total_mps_analyzed']
                    self.log_operation("Party-Line Stats (Forced)", "COMPLETED", f"{mp_count} MPs analyzed")
                    return True
                else:
                    self.log_operation("Party-Line Stats (Forced)", "FAILED", "Could not save cache")
                    return False
            else:
                self.log_operation("Party-Line Stats (Forced)", "FAILED", "No data calculated")
                return False
                
        except Exception as e:
            self.log_operation("Party-Line Stats (Forced)", "FAILED", f"Error: {e}")
            self.logger.error(f"Forced party-line stats update error: {e}")
            return False
    
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
        
        # First check for new votes and expire related caches if needed
        new_votes_detected = self.check_for_new_votes()
        if new_votes_detected:
            self.logger.info("New votes detected - proceeding with cache updates")
        
        # Update in optimal order (dependencies first)
        self.update_politicians_cache()
        self.update_votes_cache()
        self.update_vote_details_incremental()
        self.update_bills_cache()
        self.update_mp_voting_records(max_mps=max_mps)
        self.update_historical_mps()
        self.update_debates_cache()
        self.update_mp_debates_cache(max_mps=max_mps)
        self.update_mp_images_cache()
        self.update_party_line_stats()
        
        self.save_statistics()
    
    def run_incremental_mode(self, max_mps=None):
        """Run incremental updates only"""
        self.logger.info("Starting unified cache update (INCREMENTAL mode)")
        
        self.update_vote_details_incremental()
        # In incremental mode, only update fresh MP records if cache is expired
        # This will still process all MPs, but only those with expired cache
        self.update_mp_voting_records(max_mps=max_mps)
        self.update_mp_debates_cache(max_mps=max_mps)
        self.update_party_line_stats()
        
        self.save_statistics()
    
    def run_full_mode(self, max_mps=None):
        """Run full cache rebuild"""
        self.logger.info("Starting unified cache update (FULL mode)")
        
        # Force all updates
        self.force_full = True
        self.run_auto_mode(max_mps=max_mps)
    
    def run_party_line_mode(self):
        """Run only party-line statistics update"""
        self.logger.info("Starting unified cache update (PARTY-LINE mode)")
        
        # Force party-line update
        self.force_full = True
        self.update_party_line_stats()
        
        self.save_statistics()
    
    def run_politicians_mode(self):
        """Run only politicians cache update"""
        self.logger.info("Starting unified cache update (POLITICIANS mode)")
        
        self.force_full = True
        self.update_politicians_cache()
        
        self.save_statistics()
    
    def run_votes_mode(self):
        """Run only votes cache update"""
        self.logger.info("Starting unified cache update (VOTES mode)")
        
        self.force_full = True
        self.update_votes_cache()
        
        self.save_statistics()
    
    def run_vote_details_mode(self):
        """Run only vote details cache update"""
        self.logger.info("Starting unified cache update (VOTE-DETAILS mode)")
        
        self.force_full = True
        self.update_vote_details_incremental()
        
        self.save_statistics()
    
    def run_bills_mode(self):
        """Run only bills cache update"""
        self.logger.info("Starting unified cache update (BILLS mode)")
        
        self.force_full = True
        self.update_bills_cache()
        
        self.save_statistics()
    
    def run_mp_votes_mode(self, max_mps=None):
        """Run only MP voting records cache update"""
        self.logger.info("Starting unified cache update (MP-VOTES mode)")
        
        self.force_full = True
        self.update_mp_voting_records(max_mps=max_mps)
        
        self.save_statistics()
    
    def run_historical_mps_mode(self):
        """Run only historical MPs cache update"""
        self.logger.info("Starting unified cache update (HISTORICAL-MPS mode)")
        
        self.force_full = True
        self.update_historical_mps()
        
        self.save_statistics()
    
    def run_images_mode(self):
        """Run only MP images cache update"""
        self.logger.info("Starting unified cache update (IMAGES mode)")
        
        self.force_full = True
        self.update_mp_images_cache()
        
        self.save_statistics()
    
    def run_debates_mode(self):
        """Run only debates cache update"""
        self.logger.info("Starting unified cache update (DEBATES mode)")
        
        self.force_full = True
        self.update_debates_cache()
        
        self.save_statistics()
    
    def run_mp_debates_mode(self, max_mps=None):
        """Run only MP debates cache update"""
        self.logger.info("Starting unified cache update (MP-DEBATES mode)")
        
        self.force_full = True
        self.update_mp_debates_cache(max_mps=max_mps)
        
        self.save_statistics()
    
    def restart_backend_container(self):
        """Restart the backend Docker container to reload cached data"""
        try:
            import subprocess
            
            # Check if we're running in a Docker environment
            if os.path.exists('/.dockerenv'):
                self.logger.info("Running inside Docker container, skipping backend restart")
                return True
            
            # Check if docker-compose.yml exists in parent directory
            compose_file = '/home/root/mp-monitor/docker-compose.yml'
            if not os.path.exists(compose_file):
                self.logger.warning(f"Docker compose file not found at {compose_file}, skipping backend restart")
                return False
            
            self.logger.info("Restarting backend container to reload cache...")
            
            # Run docker compose restart backend
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, 'restart', 'backend'],
                cwd='/home/root/mp-monitor',
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.logger.info("Backend container restarted successfully")
                return True
            else:
                self.logger.warning(f"Failed to restart backend container: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.warning("Backend container restart timed out")
            return False
        except Exception as e:
            self.logger.warning(f"Error restarting backend container: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Unified Cache Update Script')
    parser.add_argument('--mode', choices=['auto', 'incremental', 'full', 'party-line', 'politicians', 'votes', 'vote-details', 'bills', 'mp-votes', 'historical-mps', 'images', 'debates', 'mp-debates'], default='auto',
                       help='Update mode: auto (smart), incremental (new data only), full (rebuild all), party-line (only party line stats), politicians (only politicians cache), votes (only votes cache), vote-details (only vote details cache), bills (only bills cache), mp-votes (only MP voting records), historical-mps (only historical MPs cache), images (only MP profile images), debates (only debates cache), mp-debates (only MP debates cache)')
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
        elif args.mode == 'party-line':
            updater.run_party_line_mode()
        elif args.mode == 'politicians':
            updater.run_politicians_mode()
        elif args.mode == 'votes':
            updater.run_votes_mode()
        elif args.mode == 'vote-details':
            updater.run_vote_details_mode()
        elif args.mode == 'bills':
            updater.run_bills_mode()
        elif args.mode == 'mp-votes':
            updater.run_mp_votes_mode(max_mps=args.max_mps)
        elif args.mode == 'historical-mps':
            updater.run_historical_mps_mode()
        elif args.mode == 'images':
            updater.run_images_mode()
        elif args.mode == 'debates':
            updater.run_debates_mode()
        elif args.mode == 'mp-debates':
            updater.run_mp_debates_mode(max_mps=args.max_mps)
        
        # Restart backend container after successful cache update
        updater.restart_backend_container()
            
    except KeyboardInterrupt:
        updater.logger.info("Cache update interrupted by user")
        updater.release_lock()
    except Exception as e:
        updater.logger.error(f"Cache update failed: {e}")
        updater.release_lock()
        raise
    finally:
        updater.release_lock()

if __name__ == "__main__":
    main()
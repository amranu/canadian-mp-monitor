#!/usr/bin/env python3
"""
Cache status checker for the Canadian MP Monitor
"""

import json
import os
from datetime import datetime
import time

CACHE_DIR = 'cache'
POLITICIANS_CACHE_FILE = os.path.join(CACHE_DIR, 'politicians.json')
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, 'votes.json')
MP_VOTES_CACHE_DIR = os.path.join(CACHE_DIR, 'mp_votes')

def check_cache_file(file_path, name):
    """Check status of a cache file"""
    if not os.path.exists(file_path):
        return f"❌ {name}: Not found"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        updated = data.get('updated', 'Unknown')
        count = data.get('count', len(data.get('data', [])))
        expires = data.get('expires', 0)
        
        if expires > time.time():
            status = "✅ Valid"
        else:
            status = "⚠️ Expired"
        
        return f"{status} {name}: {count} items, updated {updated}"
    
    except Exception as e:
        return f"❌ {name}: Error reading file - {e}"

def main():
    print("=== Canadian MP Monitor Cache Status ===")
    print(f"Checked at: {datetime.now().isoformat()}")
    print()
    
    # Check main cache files
    print(check_cache_file(POLITICIANS_CACHE_FILE, "Politicians"))
    print(check_cache_file(VOTES_CACHE_FILE, "Votes"))
    
    # Check MP votes cache
    if os.path.exists(MP_VOTES_CACHE_DIR):
        mp_files = [f for f in os.listdir(MP_VOTES_CACHE_DIR) if f.endswith('.json')]
        valid_mp_caches = 0
        expired_mp_caches = 0
        
        for mp_file in mp_files:
            file_path = os.path.join(MP_VOTES_CACHE_DIR, mp_file)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                expires = data.get('expires', 0)
                if expires > time.time():
                    valid_mp_caches += 1
                else:
                    expired_mp_caches += 1
            except:
                expired_mp_caches += 1
        
        if valid_mp_caches > 0:
            print(f"✅ MP Votes: {valid_mp_caches} valid caches, {expired_mp_caches} expired")
        else:
            print(f"⚠️ MP Votes: {expired_mp_caches} expired caches")
    else:
        print("❌ MP Votes: Directory not found")

if __name__ == "__main__":
    main()
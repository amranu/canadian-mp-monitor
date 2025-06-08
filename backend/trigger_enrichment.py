#!/usr/bin/env python3
"""
Trigger bill enrichment using the existing backend function
"""

import requests
import json
import os
import time
from datetime import datetime

# Import the existing functions
from app import (
    enrich_bills_with_sponsor_info, 
    load_all_bills, 
    save_cache_to_file,
    BILLS_CACHE_FILE
)

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def main():
    """Trigger enrichment using existing functions"""
    start_time = datetime.now()
    log("=== Starting Bill Enrichment using Backend Functions ===")
    
    try:
        # Load bills using existing function
        log("Loading bills from API...")
        all_bills = load_all_bills()
        log(f"Loaded {len(all_bills)} bills")
        
        # Enrich with more sessions
        target_sessions = ['45-1', '44-1', '43-2', '43-1', '42-1']
        log(f"Enriching bills for sessions: {target_sessions}")
        
        enriched_bills = enrich_bills_with_sponsor_info(all_bills, target_sessions=target_sessions)
        
        # Save to cache file
        cache_data = {
            'data': enriched_bills,
            'expires': time.time() + 10800,  # 3 hours
            'updated': datetime.now().isoformat(),
            'enrichment_note': f'Enriched sessions: {target_sessions}'
        }
        
        if save_cache_to_file(cache_data, BILLS_CACHE_FILE):
            log("Successfully saved enriched bills cache")
        else:
            log("Failed to save enriched bills cache")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        log(f"=== Enrichment Complete ===")
        log(f"Total time: {duration:.1f} seconds")
        log(f"Bills processed: {len(all_bills)}")
        log(f"Sessions targeted: {target_sessions}")
        
    except Exception as e:
        log(f"Error during enrichment: {e}")
        raise

if __name__ == "__main__":
    main()
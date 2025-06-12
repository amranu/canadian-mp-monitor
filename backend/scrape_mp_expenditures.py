#!/usr/bin/env python3
"""
MP Expenditure Scraper for ourcommons.ca

This script scrapes Members of Parliament expenditure data from the House of Commons
official disclosure website and saves it in JSON format for the MP Monitor application.

Author: Claude Code Assistant
"""

import requests
import json
import time
import re
import os
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, quote
from datetime import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Setup logging 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cache/mp_expenditures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MPExpendituresScraper:
    def __init__(self):
        self.base_url = "https://www.ourcommons.ca"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MP-Monitor-Expenditures/1.0 (amranu@gmail.com)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-CA,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Ensure cache directory exists
        os.makedirs('cache', exist_ok=True)
        os.makedirs('cache/expenditures', exist_ok=True)
        
        self.mps_data = []
        self.expenditures_data = []
        self.failed_mps = []
        
    def get_mp_list_from_openparliament(self):
        """Get MP list from existing OpenParliament cache if available"""
        try:
            with open('cache/politicians.json', 'r', encoding='utf-8') as f:
                politicians_data = json.load(f)
                
            mps = []
            for politician in politicians_data.get('objects', []):
                if politician.get('current', False):
                    mps.append({
                        'name': politician.get('name', ''),
                        'slug': politician.get('slug', ''),
                        'party': politician.get('party', {}).get('short_name', ''),
                        'riding': politician.get('riding', {}).get('name', ''),
                        'province': politician.get('riding', {}).get('province', '')
                    })
            
            logger.info(f"Loaded {len(mps)} MPs from OpenParliament cache")
            return mps
            
        except FileNotFoundError:
            logger.warning("OpenParliament politicians cache not found, will discover MPs manually")
            return []
        except Exception as e:
            logger.error(f"Error loading OpenParliament cache: {e}")
            return []
    
    def discover_mp_ids_from_search(self):
        """Discover MP IDs by parsing the search page for member links"""
        logger.info("Discovering MP IDs from ourcommons.ca search page...")
        
        search_url = f"{self.base_url}/members/en/search"
        
        try:
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            # Extract MP links using regex to find /members/en/name(id) patterns
            import re
            
            # Pattern to match /members/en/name(id) links
            member_pattern = r'/members/en/([^(]+)\((\d+)\)'
            matches = re.findall(member_pattern, response.text)
            
            found_mps = []
            for name_slug, numeric_id in matches:
                found_mps.append({
                    'name_slug': name_slug,
                    'numeric_id': numeric_id,
                    'name': name_slug.replace('-', ' ').title()
                })
            
            logger.info(f"Found {len(found_mps)} MP links from search page")
            
            if found_mps:
                return self.get_uuid_member_ids(found_mps)
            else:
                logger.warning("No MP links found, trying iteration method")
                return self.discover_mp_ids_by_iteration()
            
        except Exception as e:
            logger.error(f"Error accessing members search: {e}")
            return self.discover_mp_ids_by_iteration()
    
    def get_uuid_member_ids(self, mp_list):
        """Get UUID member IDs by visiting individual MP pages"""
        logger.info(f"Getting UUID member IDs for {len(mp_list)} MPs...")
        
        found_mps = []
        
        for i, mp_info in enumerate(mp_list):  # Process all MPs
            try:
                mp_url = f"{self.base_url}/members/en/{mp_info['name_slug']}({mp_info['numeric_id']})"
                logger.info(f"Fetching UUID for {mp_info['name']} ({i+1}/{len(mp_list)})")
                
                response = self.session.get(mp_url, timeout=15)
                response.raise_for_status()
                
                # Look for ProactiveDisclosure memberId UUID
                import re
                uuid_pattern = r'memberId=([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})'
                uuid_match = re.search(uuid_pattern, response.text, re.IGNORECASE)
                
                if uuid_match:
                    uuid = uuid_match.group(1)
                    found_mps.append({
                        'member_id': uuid,
                        'name': mp_info['name'],
                        'name_slug': mp_info['name_slug'],
                        'numeric_id': mp_info['numeric_id']
                    })
                    logger.info(f"Found UUID {uuid} for {mp_info['name']}")
                else:
                    logger.warning(f"No UUID found for {mp_info['name']}")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error getting UUID for {mp_info['name']}: {e}")
                continue
        
        logger.info(f"Successfully found UUIDs for {len(found_mps)} MPs")
        return found_mps
    
    def discover_mp_ids_by_iteration(self):
        """Discover MP IDs by trying common ID patterns"""
        logger.info("Attempting to discover MP IDs by iteration...")
        
        found_mps = []
        
        # Try MP IDs from 1 to 500 (reasonable range)
        for mp_id in range(1, 501):
            if len(found_mps) >= 350:  # Stop after finding reasonable number
                break
                
            try:
                # Test if MP exists by trying to access their expenditure page
                test_url = f"{self.base_url}/PublicDisclosure/MemberExpenditures.aspx"
                params = {
                    'Id': 'Dynamic',
                    'Language': 'E', 
                    'View': 'M',
                    'MemberId': str(mp_id),
                    'FormatType': 'XML'
                }
                
                response = self.session.get(test_url, params=params, timeout=10)
                
                if response.status_code == 200 and len(response.content) > 100:
                    # Try to parse the XML to get MP info
                    try:
                        root = ET.fromstring(response.content)
                        mp_name = root.find('.//Name')
                        mp_party = root.find('.//MemberParty')
                        constituency = root.find('.//ConstituencyName')
                        
                        if mp_name is not None:
                            found_mps.append({
                                'member_id': mp_id,
                                'name': mp_name.text if mp_name.text else f"Unknown MP {mp_id}",
                                'party': mp_party.text if mp_party and mp_party.text else 'Unknown',
                                'constituency': constituency.text if constituency and constituency.text else 'Unknown'
                            })
                            logger.info(f"Found MP {mp_id}: {mp_name.text if mp_name.text else 'Unknown'}")
                    except ET.ParseError:
                        pass
                
                # Rate limiting
                time.sleep(0.2)
                
            except Exception as e:
                logger.debug(f"MP ID {mp_id} failed: {e}")
                continue
        
        logger.info(f"Discovered {len(found_mps)} MPs through iteration")
        return found_mps
    
    def fetch_mp_expenditures(self, mp_info):
        """Fetch expenditure data for a single MP using ProactiveDisclosure"""
        mp_id = mp_info.get('member_id')
        mp_name = mp_info.get('name', f'MP {mp_id}')
        
        try:
            logger.info(f"Fetching expenditures for {mp_name} (UUID: {mp_id})")
            
            # Use the ProactiveDisclosure URL format
            url = f"{self.base_url}/ProactiveDisclosure/en/members"
            params = {
                'memberId': mp_id
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            if len(response.content) < 100:
                logger.warning(f"Empty or minimal response for {mp_name}")
                return None
            
            # The ProactiveDisclosure page returns HTML, not XML
            # We need to parse the HTML to extract expenditure data
            mp_data = {
                'member_id': mp_id,
                'scraped_at': datetime.now().isoformat(),
                'name': mp_name,
                'name_slug': mp_info.get('name_slug', ''),
                'numeric_id': mp_info.get('numeric_id', ''),
                'expenditures': [],
                'raw_response_length': len(response.content)
            }
            
            # For now, store the HTML response to analyze structure
            # We'll need to parse tables or structured data from the HTML
            import re
            
            # Look for expenditure tables or data in the HTML
            # This is a simplified approach - we'd need to analyze the actual HTML structure
            expenditure_pattern = r'expenditure|expense|cost|amount|total'
            matches = re.findall(expenditure_pattern, response.text, re.IGNORECASE)
            
            mp_data['expenditure_mentions'] = len(matches)
            
            # Store first 1000 chars of response for analysis
            mp_data['response_preview'] = response.text[:1000]
            
            logger.info(f"Successfully fetched expenditure page for {mp_name} ({len(response.content)} bytes, {len(matches)} expenditure mentions)")
            return mp_data
            
        except requests.RequestException as e:
            logger.error(f"Request error for {mp_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {mp_name}: {e}")
            return None
    
    def scrape_all_expenditures(self, max_workers=3):
        """Scrape expenditures for all discovered MPs"""
        
        # First try to get MP list from OpenParliament cache
        mps_from_cache = self.get_mp_list_from_openparliament()
        
        if not mps_from_cache:
            # Discover MPs manually
            self.mps_data = self.discover_mp_ids_from_search()
        else:
            # Use cached MP data but we still need to discover member IDs
            logger.info("Using OpenParliament MP list, discovering member IDs...")
            self.mps_data = self.discover_mp_ids_by_iteration()
        
        if not self.mps_data:
            logger.error("No MPs discovered. Cannot proceed with expenditure scraping.")
            return False
        
        logger.info(f"Starting expenditure scraping for {len(self.mps_data)} MPs")
        
        # Use ThreadPoolExecutor for concurrent scraping
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_mp = {
                executor.submit(self.fetch_mp_expenditures, mp_info): mp_info 
                for mp_info in self.mps_data
            }
            
            # Process completed tasks
            for future in as_completed(future_to_mp):
                mp_info = future_to_mp[future]
                try:
                    result = future.result()
                    if result:
                        self.expenditures_data.append(result)
                    else:
                        self.failed_mps.append(mp_info)
                        
                except Exception as e:
                    logger.error(f"Task failed for {mp_info.get('name', 'Unknown MP')}: {e}")
                    self.failed_mps.append(mp_info)
                
                # Rate limiting between requests
                time.sleep(0.1)
        
        logger.info(f"Scraping completed. Success: {len(self.expenditures_data)}, Failed: {len(self.failed_mps)}")
        return True
    
    def save_data(self):
        """Save scraped expenditure data to JSON files"""
        
        # Main expenditures file
        output_file = 'cache/expenditures/mp_expenditures.json'
        
        output_data = {
            'scraped_at': datetime.now().isoformat(),
            'total_mps': len(self.expenditures_data),
            'failed_mps': len(self.failed_mps),
            'data': self.expenditures_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved expenditure data to {output_file}")
        
        # Save failed MPs list for debugging
        if self.failed_mps:
            failed_file = 'cache/expenditures/failed_mps.json'
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_mps, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved failed MPs list to {failed_file}")
        
        # Create summary report
        summary = {
            'scraping_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_mps_attempted': len(self.mps_data),
                'successful_scrapes': len(self.expenditures_data),
                'failed_scrapes': len(self.failed_mps),
                'success_rate': f"{(len(self.expenditures_data) / len(self.mps_data) * 100):.1f}%" if self.mps_data else "0%"
            }
        }
        
        summary_file = 'cache/expenditures/scraping_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Scrape MP expenditure data from ourcommons.ca')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers (default: 3)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = MPExpendituresScraper()
    
    try:
        logger.info("Starting MP expenditures scraping...")
        
        success = scraper.scrape_all_expenditures(max_workers=args.workers)
        
        if success and scraper.expenditures_data:
            output_file = scraper.save_data()
            
            logger.info("="*50)
            logger.info("SCRAPING COMPLETED SUCCESSFULLY")
            logger.info(f"Total MPs scraped: {len(scraper.expenditures_data)}")
            logger.info(f"Failed scrapes: {len(scraper.failed_mps)}")
            logger.info(f"Output file: {output_file}")
            logger.info("="*50)
            
        else:
            logger.error("Scraping failed or no data collected")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        if scraper.expenditures_data:
            logger.info("Saving partial data...")
            scraper.save_data()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
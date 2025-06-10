#!/usr/bin/env python3
"""
MP Expenditure Table Scraper for ourcommons.ca

This script scrapes the tabular expenditure data from the House of Commons
ProactiveDisclosure page which shows all MPs' expenditures for a given period.

Author: Claude Code Assistant
"""

import requests
import json
import time
import os
import re
from datetime import datetime
import argparse
from bs4 import BeautifulSoup
import logging

# Setup logging 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cache/mp_expenditures_table.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MPExpenditureTableScraper:
    def __init__(self):
        self.base_url = "https://www.ourcommons.ca"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MP-Monitor-Expenditures/1.0 (Educational Research)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-CA,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Ensure cache directory exists
        os.makedirs('cache', exist_ok=True)
        os.makedirs('cache/expenditures', exist_ok=True)
        
        self.expenditures_data = []
        
    def get_available_quarters(self):
        """Get available quarterly reports from the main page"""
        logger.info("Fetching available quarters...")
        
        url = f"{self.base_url}/ProactiveDisclosure/en/members"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            quarters = []
            
            # Look for links to quarterly reports
            # Pattern: links containing "Quarter Report" or specific date ranges
            links = soup.find_all('a', href=True)
            
            for link in links:
                text = link.get_text().strip()
                href = link.get('href', '')
                
                # Look for quarterly report patterns
                if any(pattern in text.lower() for pattern in [
                    'quarter report', 'quarterly report', 'q1', 'q2', 'q3', 'q4'
                ]):
                    # Extract date range if present
                    date_match = re.search(r'\(([^)]+)\)', text)
                    date_range = date_match.group(1) if date_match else ''
                    
                    quarters.append({
                        'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        'text': text,
                        'date_range': date_range
                    })
            
            # Also look for select/option elements
            selects = soup.find_all('select')
            for select in selects:
                options = select.find_all('option')
                for option in options:
                    value = option.get('value', '')
                    text = option.get_text().strip()
                    
                    if value and any(pattern in text.lower() for pattern in [
                        'quarter', 'q1', 'q2', 'q3', 'q4', '2024', '2023'
                    ]):
                        quarters.append({
                            'value': value,
                            'text': text,
                            'type': 'select_option'
                        })
            
            # Remove duplicates based on text
            seen_texts = set()
            unique_quarters = []
            for quarter in quarters:
                if quarter['text'] not in seen_texts:
                    seen_texts.add(quarter['text'])
                    unique_quarters.append(quarter)
            
            logger.info(f"Found {len(unique_quarters)} available quarters/periods")
            for quarter in unique_quarters[:5]:  # Log first few
                logger.info(f"  - {quarter['text']}")
            
            return unique_quarters
            
        except Exception as e:
            logger.error(f"Error fetching available quarters: {e}")
            return []
    
    def scrape_expenditures_for_period(self, quarter_info=None):
        """Scrape expenditures table for a specific period"""
        if quarter_info is None:
            quarter_info = {'text': 'Current Period', 'url': None}
        
        period_text = quarter_info.get('text', 'Unknown Period')
        logger.info(f"Scraping expenditures for period: {period_text}")
        
        # Use specific URL if provided, otherwise default
        if quarter_info.get('url'):
            url = quarter_info['url']
        elif quarter_info.get('value'):
            # Handle select option values
            url = f"{self.base_url}/ProactiveDisclosure/en/members"
            params = {'period': quarter_info['value']}
        else:
            # Default to current period
            url = f"{self.base_url}/ProactiveDisclosure/en/members"
            params = {}
        
        try:
            if quarter_info.get('url'):
                response = self.session.get(url, timeout=30)
            else:
                response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the expenditures table
            expenditures_table = self.find_expenditures_table(soup)
            
            if not expenditures_table:
                logger.warning(f"No expenditures table found for period {period_text}")
                return []
            
            # Parse the table
            expenditures = self.parse_expenditures_table(expenditures_table, period_text)
            logger.info(f"Parsed {len(expenditures)} MP expenditure records for {period_text}")
            
            return expenditures
            
        except Exception as e:
            logger.error(f"Error scraping expenditures for period {period_text}: {e}")
            return []
    
    def find_expenditures_table(self, soup):
        """Find the main expenditures table in the HTML"""
        
        # Look for tables with expenditure-related content
        tables = soup.find_all('table')
        
        for table in tables:
            # Check table headers for expenditure columns
            headers = table.find_all(['th', 'td'])
            header_text = ' '.join([h.get_text().strip().lower() for h in headers])
            
            if any(keyword in header_text for keyword in [
                'salaries', 'travel', 'hospitality', 'contracts', 
                'constituency', 'caucus', 'expenditure'
            ]):
                logger.info("Found expenditures table")
                return table
        
        # Alternative: look for divs or sections with expenditure data
        expenditure_sections = soup.find_all(['div', 'section'], 
                                           class_=re.compile(r'expenditure|disclosure|financial', re.I))
        
        for section in expenditure_sections:
            table = section.find('table')
            if table:
                logger.info("Found expenditures table in section")
                return table
        
        logger.warning("No expenditures table found")
        return None
    
    def parse_expenditures_table(self, table, period_text):
        """Parse the expenditures table and extract MP data"""
        expenditures = []
        
        # Find table headers
        header_row = table.find('tr')
        if not header_row:
            logger.error("No header row found in table")
            return []
        
        headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]
        logger.info(f"Table headers: {headers}")
        
        # Find data rows
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(headers):
                continue
            
            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    header = headers[i].lower().strip()
                    value = cell.get_text().strip()
                    
                    # Clean up monetary values
                    if '$' in value:
                        # Extract numeric value from currency
                        numeric_value = re.sub(r'[^0-9.-]', '', value)
                        try:
                            row_data[f"{header}_amount"] = float(numeric_value) if numeric_value else 0.0
                        except ValueError:
                            row_data[f"{header}_amount"] = 0.0
                        row_data[f"{header}_formatted"] = value
                    else:
                        row_data[header] = value
            
            # Add metadata
            row_data['period'] = period_text
            row_data['scraped_at'] = datetime.now().isoformat()
            
            # Only add if we have meaningful data
            if any(key.endswith('_amount') for key in row_data.keys()):
                expenditures.append(row_data)
        
        return expenditures
    
    def scrape_all_periods(self):
        """Scrape expenditures for all available periods"""
        logger.info("Starting comprehensive expenditure scraping...")
        
        # Get available periods
        quarters = self.get_available_quarters()
        
        if not quarters:
            logger.info("No specific periods found, scraping current period...")
            quarters = [{'value': None, 'text': 'Current Period'}]
        
        all_expenditures = []
        
        for quarter in quarters[:3]:  # Limit to 3 most recent periods for testing
            logger.info(f"Processing period: {quarter['text']}")
            
            period_expenditures = self.scrape_expenditures_for_period(quarter)
            
            all_expenditures.extend(period_expenditures)
            
            # Rate limiting
            time.sleep(2)
        
        self.expenditures_data = all_expenditures
        logger.info(f"Total expenditure records collected: {len(all_expenditures)}")
        
        return len(all_expenditures) > 0
    
    def normalize_mp_name_to_slug(self, mp_name):
        """Convert MP name to URL slug format"""
        # Handle "Last, First" format
        if ',' in mp_name:
            parts = mp_name.split(',')
            if len(parts) >= 2:
                last_name = parts[0].strip()
                first_name = parts[1].strip()
                full_name = f"{first_name} {last_name}"
            else:
                full_name = mp_name
        else:
            full_name = mp_name
        
        # Convert to slug: lowercase, replace spaces with hyphens, remove special chars
        slug = full_name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special characters
        slug = re.sub(r'[-\s]+', '-', slug)   # Replace spaces and multiple hyphens
        slug = slug.strip('-')                # Remove leading/trailing hyphens
        
        return slug
    
    def save_data(self):
        """Save scraped expenditure data to individual MP files"""
        
        if not self.expenditures_data:
            logger.warning("No expenditure data to save")
            return None
        
        # Create individual MP expenditure directory
        mp_expenditures_dir = 'cache/expenditures/mp_files'
        os.makedirs(mp_expenditures_dir, exist_ok=True)
        
        # Group data by MP
        mp_data = {}
        for record in self.expenditures_data:
            mp_name = record.get('name', record.get('member', 'Unknown'))
            if mp_name not in mp_data:
                mp_data[mp_name] = {
                    'mp_name': mp_name,
                    'constituency': record.get('constituency', ''),
                    'caucus': record.get('caucus', ''),
                    'name_slug': self.normalize_mp_name_to_slug(mp_name),
                    'periods': [],
                    'totals': {
                        'salaries': 0.0,
                        'travel': 0.0,
                        'hospitality': 0.0,
                        'contracts': 0.0,
                        'overall_total': 0.0
                    },
                    'scraped_at': datetime.now().isoformat()
                }
            
            mp_data[mp_name]['periods'].append(record)
            
            # Sum up expenditures
            for category in ['salaries', 'travel', 'hospitality', 'contracts']:
                amount_key = f"{category}_amount"
                if amount_key in record and isinstance(record[amount_key], (int, float)):
                    mp_data[mp_name]['totals'][category] += record[amount_key]
                    mp_data[mp_name]['totals']['overall_total'] += record[amount_key]
        
        # Save individual MP files
        saved_files = 0
        mp_slugs = []
        
        for mp_name, data in mp_data.items():
            slug = data['name_slug']
            mp_slugs.append(slug)
            
            mp_file = os.path.join(mp_expenditures_dir, f"{slug}.json")
            
            try:
                with open(mp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                saved_files += 1
                
                if saved_files <= 5:  # Log first few files
                    logger.info(f"Saved expenditure data for {mp_name} -> {slug}.json")
                
            except Exception as e:
                logger.error(f"Error saving file for {mp_name}: {e}")
        
        logger.info(f"Saved {saved_files} individual MP expenditure files")
        
        # Create index file with all MP slugs and metadata
        index_file = 'cache/expenditures/mp_expenditures_index.json'
        index_data = {
            'scraped_at': datetime.now().isoformat(),
            'total_mps': len(mp_data),
            'total_records': len(self.expenditures_data),
            'mp_slugs': sorted(mp_slugs),
            'categories': ['salaries', 'travel', 'hospitality', 'contracts'],
            'file_structure': {
                'individual_files': f"{mp_expenditures_dir}/<mp-slug>.json",
                'example': f"{mp_expenditures_dir}/ziad-aboultaif.json"
            }
        }
        
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved expenditures index to {index_file}")
        
        # Also create summary stats
        summary_file = 'cache/expenditures/mp_expenditures_summary.json'
        summary_stats = {
            'scraped_at': datetime.now().isoformat(),
            'total_mps': len(mp_data),
            'expenditure_stats': {
                'total_salaries': sum(data['totals']['salaries'] for data in mp_data.values()),
                'total_travel': sum(data['totals']['travel'] for data in mp_data.values()),
                'total_hospitality': sum(data['totals']['hospitality'] for data in mp_data.values()),
                'total_contracts': sum(data['totals']['contracts'] for data in mp_data.values()),
                'grand_total': sum(data['totals']['overall_total'] for data in mp_data.values())
            },
            'top_spenders': sorted([
                {
                    'name': data['mp_name'],
                    'slug': data['name_slug'],
                    'total': data['totals']['overall_total'],
                    'caucus': data['caucus']
                }
                for data in mp_data.values()
            ], key=lambda x: x['total'], reverse=True)[:10]
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved expenditure summary stats to {summary_file}")
        
        return index_file

def main():
    parser = argparse.ArgumentParser(description='Scrape MP expenditure table data from ourcommons.ca')
    parser.add_argument('--period', type=str, help='Specific period to scrape')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = MPExpenditureTableScraper()
    
    try:
        logger.info("Starting MP expenditures table scraping...")
        
        if args.period:
            # Scrape specific period
            expenditures = scraper.scrape_expenditures_for_period(args.period, args.period)
            scraper.expenditures_data = expenditures
        else:
            # Scrape all available periods
            success = scraper.scrape_all_periods()
            if not success:
                logger.error("Failed to scrape any expenditure data")
                return
        
        if scraper.expenditures_data:
            output_file = scraper.save_data()
            
            logger.info("="*50)
            logger.info("SCRAPING COMPLETED SUCCESSFULLY")
            logger.info(f"Total records scraped: {len(scraper.expenditures_data)}")
            logger.info(f"Output file: {output_file}")
            logger.info("="*50)
            
        else:
            logger.error("No expenditure data collected")
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        if scraper.expenditures_data:
            logger.info("Saving partial data...")
            scraper.save_data()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
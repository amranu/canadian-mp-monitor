#!/usr/bin/env python3
"""
Historical MP Expenditure Scraper for ourcommons.ca

This script scrapes historical expenditure data across multiple fiscal years
to provide comprehensive expenditure records for long-serving MPs.

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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cache/historical_expenditures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HistoricalExpenditureScraper:
    def __init__(self):
        self.base_url = "https://www.ourcommons.ca"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MP-Monitor-Historical-Expenditures/1.0 (Educational Research)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-CA,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Ensure cache directory exists
        os.makedirs('cache', exist_ok=True)
        os.makedirs('cache/expenditures', exist_ok=True)
        os.makedirs('cache/expenditures/mp_files', exist_ok=True)
        
        self.all_expenditures = {}  # {mp_slug: [periods...]}
        
    def generate_historical_periods(self, start_fiscal_year=2019, end_fiscal_year=2025):
        """Generate fiscal year/quarter combinations to scrape"""
        periods = []
        
        for fiscal_year in range(start_fiscal_year, end_fiscal_year + 1):
            for quarter in range(1, 5):  # Quarters 1-4
                periods.append({
                    'fiscal_year': fiscal_year,
                    'quarter': quarter,
                    'url': f"/ProactiveDisclosure/en/members/{fiscal_year}/{quarter}",
                    'description': f"FY {fiscal_year-1}-{fiscal_year} Q{quarter}"
                })
        
        logger.info(f"Generated {len(periods)} historical periods to scrape")
        return periods
    
    def scrape_period_expenditures(self, period_info):
        """Scrape expenditures for a specific fiscal year/quarter"""
        fiscal_year = period_info['fiscal_year']
        quarter = period_info['quarter']
        description = period_info['description']
        
        logger.info(f"Scraping {description}...")
        
        url = f"{self.base_url}{period_info['url']}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the expenditures table
            expenditures_table = self.find_expenditures_table(soup)
            
            if not expenditures_table:
                logger.warning(f"No expenditures table found for {description}")
                return {}
            
            # Parse the table
            period_expenditures = self.parse_expenditures_table(expenditures_table, period_info)
            logger.info(f"Parsed {len(period_expenditures)} MP records for {description}")
            
            return period_expenditures
            
        except requests.RequestException as e:
            logger.warning(f"Request failed for {description}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error scraping {description}: {e}")
            return {}
    
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
                return table
        
        return None
    
    def parse_expenditures_table(self, table, period_info):
        """Parse the expenditures table and extract MP data"""
        expenditures = {}
        
        rows = table.find_all('tr')
        if not rows:
            return expenditures
        
        # Find header row to determine column indices
        header_row = rows[0]
        headers = [th.get_text().strip().lower() for th in header_row.find_all(['th', 'td'])]
        
        # Map column names to indices
        column_map = {}
        for i, header in enumerate(headers):
            if 'name' in header or 'member' in header:
                column_map['name'] = i
            elif 'constituency' in header or 'riding' in header:
                column_map['constituency'] = i
            elif 'caucus' in header or 'party' in header:
                column_map['caucus'] = i
            elif 'salaries' in header:
                column_map['salaries'] = i
            elif 'travel' in header:
                column_map['travel'] = i
            elif 'hospitality' in header:
                column_map['hospitality'] = i
            elif 'contracts' in header:
                column_map['contracts'] = i
        
        logger.debug(f"Column mapping: {column_map}")
        
        # Parse data rows
        for row in rows[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(column_map):
                continue
            
            try:
                # Extract MP data
                mp_name = cells[column_map.get('name', 0)].get_text().strip()
                constituency = cells[column_map.get('constituency', 1)].get_text().strip()
                caucus = cells[column_map.get('caucus', 2)].get_text().strip()
                
                # Skip empty rows or headers
                if not mp_name or mp_name.lower() in ['name', 'member', 'total']:
                    continue
                
                # Extract expenditure amounts
                salaries_text = cells[column_map.get('salaries', 3)].get_text().strip()
                travel_text = cells[column_map.get('travel', 4)].get_text().strip()
                hospitality_text = cells[column_map.get('hospitality', 5)].get_text().strip()
                contracts_text = cells[column_map.get('contracts', 6)].get_text().strip()
                
                # Parse monetary amounts
                salaries_amount = self.parse_currency(salaries_text)
                travel_amount = self.parse_currency(travel_text)
                hospitality_amount = self.parse_currency(hospitality_text)
                contracts_amount = self.parse_currency(contracts_text)
                
                # Generate MP slug
                name_slug = self.normalize_mp_name_to_slug(mp_name)
                
                # Create period data
                period_data = {
                    'name': mp_name,
                    'constituency': constituency,
                    'caucus': caucus,
                    'salaries_amount': salaries_amount,
                    'salaries_formatted': self.format_currency(salaries_amount),
                    'travel_amount': travel_amount,
                    'travel_formatted': self.format_currency(travel_amount),
                    'hospitality_amount': hospitality_amount,
                    'hospitality_formatted': self.format_currency(hospitality_amount),
                    'contracts_amount': contracts_amount,
                    'contracts_formatted': self.format_currency(contracts_amount),
                    'fiscal_year': period_info['fiscal_year'],
                    'quarter': period_info['quarter'],
                    'period_description': period_info['description'],
                    'scraped_at': datetime.now().isoformat()
                }
                
                expenditures[name_slug] = period_data
                
            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
                continue
        
        return expenditures
    
    def parse_currency(self, text):
        """Parse currency text to float"""
        if not text:
            return 0.0
        
        # Remove currency symbols, commas, spaces
        clean_text = re.sub(r'[^\d.-]', '', text)
        
        try:
            return float(clean_text) if clean_text else 0.0
        except ValueError:
            return 0.0
    
    def format_currency(self, amount):
        """Format amount as currency"""
        return f"${amount:,.2f}"
    
    def normalize_mp_name_to_slug(self, mp_name):
        """Convert MP name to URL slug format"""
        if not mp_name:
            return 'unknown'
        
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
        
        # Remove titles and honorifics
        full_name = re.sub(r'\b(hon\.?|right hon\.?|mr\.?|mrs\.?|ms\.?|dr\.?)\s*', '', full_name, flags=re.IGNORECASE)
        
        # Convert to slug
        slug = full_name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars except hyphens
        slug = re.sub(r'[-\s]+', '-', slug)  # Replace spaces/multiple hyphens with single hyphen
        slug = slug.strip('-')  # Remove leading/trailing hyphens
        
        return slug
    
    def scrape_all_historical_periods(self, max_workers=3, periods=None):
        """Scrape expenditures for all historical periods"""
        
        # Generate periods to scrape (last 6 years)
        if periods is None:
            periods = self.generate_historical_periods(2019, 2025)
        
        logger.info(f"Starting historical expenditure scraping for {len(periods)} periods...")
        
        # Use ThreadPoolExecutor for concurrent scraping
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_period = {
                executor.submit(self.scrape_period_expenditures, period): period 
                for period in periods
            }
            
            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_period):
                period = future_to_period[future]
                try:
                    period_expenditures = future.result()
                    
                    # Merge data into all_expenditures
                    for mp_slug, expenditure_data in period_expenditures.items():
                        if mp_slug not in self.all_expenditures:
                            self.all_expenditures[mp_slug] = []
                        self.all_expenditures[mp_slug].append(expenditure_data)
                    
                    completed += 1
                    logger.info(f"Completed {completed}/{len(periods)}: {period['description']}")
                    
                except Exception as e:
                    logger.error(f"Task failed for {period['description']}: {e}")
                
                # Rate limiting between requests
                time.sleep(0.2)
        
        logger.info(f"Historical scraping completed. Collected data for {len(self.all_expenditures)} MPs")
        return True
    
    def calculate_mp_totals(self, periods):
        """Calculate total expenditures across all periods for an MP"""
        totals = {
            'salaries': 0,
            'travel': 0,
            'hospitality': 0,
            'contracts': 0
        }
        
        for period in periods:
            totals['salaries'] += period.get('salaries_amount', 0)
            totals['travel'] += period.get('travel_amount', 0)
            totals['hospitality'] += period.get('hospitality_amount', 0)
            totals['contracts'] += period.get('contracts_amount', 0)
        
        totals['overall_total'] = sum(totals.values())
        return totals
    
    def save_individual_mp_files(self):
        """Save individual MP expenditure files with historical data"""
        
        mp_files_saved = 0
        
        for mp_slug, periods in self.all_expenditures.items():
            if not periods:
                continue
                
            # Sort periods by fiscal year and quarter (newest first)
            periods.sort(key=lambda x: (x['fiscal_year'], x['quarter']), reverse=True)
            
            # Get latest MP info
            latest_period = periods[0]
            
            # Calculate totals across all periods
            totals = self.calculate_mp_totals(periods)
            
            # Create MP file data
            mp_data = {
                'mp_name': latest_period['name'],
                'constituency': latest_period['constituency'], 
                'caucus': latest_period['caucus'],
                'name_slug': mp_slug,
                'periods': periods,
                'totals': totals,
                'scraped_at': datetime.now().isoformat(),
                'historical_data': True,
                'years_covered': len(set(p['fiscal_year'] for p in periods)),
                'quarters_covered': len(periods)
            }
            
            # Save individual MP file
            mp_file_path = os.path.join('cache/expenditures/mp_files', f'{mp_slug}.json')
            
            with open(mp_file_path, 'w', encoding='utf-8') as f:
                json.dump(mp_data, f, indent=2, ensure_ascii=False)
            
            mp_files_saved += 1
            
            if mp_files_saved % 50 == 0:
                logger.info(f"Saved {mp_files_saved} MP files...")
        
        logger.info(f"Saved {mp_files_saved} individual MP expenditure files with historical data")
        return mp_files_saved
    
    def save_summary_stats(self):
        """Save updated summary statistics including historical data"""
        
        # Calculate overall statistics
        total_mps = len(self.all_expenditures)
        total_records = sum(len(periods) for periods in self.all_expenditures.values())
        
        # Calculate expenditure totals
        grand_totals = {
            'total_salaries': 0,
            'total_travel': 0,
            'total_hospitality': 0,
            'total_contracts': 0
        }
        
        mp_totals = []
        
        for mp_slug, periods in self.all_expenditures.items():
            if not periods:
                continue
                
            mp_total = self.calculate_mp_totals(periods)
            latest_period = periods[0]
            
            mp_totals.append({
                'name': latest_period['name'],
                'slug': mp_slug,
                'total': mp_total['overall_total'],
                'caucus': latest_period['caucus'],
                'years_covered': len(set(p['fiscal_year'] for p in periods)),
                'quarters_covered': len(periods)
            })
            
            grand_totals['total_salaries'] += mp_total['salaries']
            grand_totals['total_travel'] += mp_total['travel']
            grand_totals['total_hospitality'] += mp_total['hospitality']
            grand_totals['total_contracts'] += mp_total['contracts']
        
        grand_totals['grand_total'] = sum(grand_totals.values())
        
        # Create summary
        summary_stats = {
            'scraped_at': datetime.now().isoformat(),
            'total_mps': total_mps,
            'total_records': total_records,
            'historical_data': True,
            'expenditure_stats': grand_totals,
            'top_spenders': sorted(mp_totals, key=lambda x: x['total'], reverse=True)[:20],
            'fiscal_years_covered': sorted(set(
                p['fiscal_year'] for periods in self.all_expenditures.values() 
                for p in periods
            )),
            'quarters_covered': sorted(set(
                f"FY{p['fiscal_year']-1}-{p['fiscal_year']} Q{p['quarter']}" 
                for periods in self.all_expenditures.values() 
                for p in periods
            ))
        }
        
        # Save summary
        summary_file = 'cache/expenditures/historical_expenditures_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved historical expenditure summary to {summary_file}")
        return summary_file

def main():
    parser = argparse.ArgumentParser(description='Scrape historical MP expenditure data from ourcommons.ca')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers (default: 3)')
    parser.add_argument('--start-year', type=int, default=2019, help='Starting fiscal year (default: 2019)')
    parser.add_argument('--end-year', type=int, default=2025, help='Ending fiscal year (default: 2025)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = HistoricalExpenditureScraper()
    
    try:
        logger.info("Starting historical MP expenditures scraping...")
        logger.info(f"Fiscal years: {args.start_year} to {args.end_year}")
        logger.info(f"Workers: {args.workers}")
        
        # Set fiscal year range for scraping
        periods = scraper.generate_historical_periods(args.start_year, args.end_year)
        
        success = scraper.scrape_all_historical_periods(max_workers=args.workers, periods=periods)
        
        if success and scraper.all_expenditures:
            mp_files_saved = scraper.save_individual_mp_files()
            summary_file = scraper.save_summary_stats()
            
            logger.info("="*60)
            logger.info("HISTORICAL EXPENDITURE SCRAPING COMPLETED")
            logger.info(f"MPs with data: {len(scraper.all_expenditures)}")
            logger.info(f"MP files saved: {mp_files_saved}")
            logger.info(f"Total records: {sum(len(periods) for periods in scraper.all_expenditures.values())}")
            logger.info(f"Summary file: {summary_file}")
            logger.info("="*60)
            
        else:
            logger.error("Historical scraping failed or no data collected")
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        if scraper.all_expenditures:
            logger.info("Saving partial data...")
            scraper.save_individual_mp_files()
            scraper.save_summary_stats()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
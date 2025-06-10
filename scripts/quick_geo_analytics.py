#!/usr/bin/env python3
"""
Quick Geolocation Analytics for Canadian MP Monitor - Simplified Version
"""

import re
import subprocess
import json
import requests
import time
from collections import defaultdict
from datetime import datetime

def extract_top_ips_from_docker_logs(container_name="mp-monitor-nginx", hours=24, limit=20):
    """Extract top IP addresses from nginx docker logs"""
    print(f"Extracting top {limit} IPs from {container_name} logs (last {hours} hours)...")
    
    try:
        # Get nginx logs from docker container
        cmd = f"docker logs {container_name} --since {hours}h"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="/home/root/mp-monitor")
        
        if result.returncode != 0:
            print(f"Error getting docker logs: {result.stderr}")
            return {}
        
        # Extract IP addresses from log lines
        ip_pattern = r'^(\d+\.\d+\.\d+\.\d+)'
        ip_counts = defaultdict(int)
        total_requests = 0
        
        for line in result.stdout.split('\n'):
            match = re.match(ip_pattern, line.strip())
            if match:
                ip = match.group(1)
                # Skip private IP ranges
                if not is_private_ip(ip):
                    ip_counts[ip] += 1
                    total_requests += 1
        
        # Get top IPs
        top_ips = dict(sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:limit])
        
        print(f"Found {len(ip_counts)} unique public IPs, analyzing top {len(top_ips)}")
        print(f"Total requests: {total_requests:,}")
        
        return top_ips, total_requests
        
    except Exception as e:
        print(f"Error extracting IPs: {e}")
        return {}, 0

def is_private_ip(ip):
    """Check if IP is in private range"""
    octets = ip.split('.')
    if len(octets) != 4:
        return True
        
    try:
        first = int(octets[0])
        second = int(octets[1])
        
        # Private ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
        if first == 10:
            return True
        elif first == 172 and 16 <= second <= 31:
            return True
        elif first == 192 and second == 168:
            return True
        elif first == 127:  # Localhost
            return True
        
        return False
    except ValueError:
        return True

def get_geolocation_for_ips(ip_list):
    """Get geolocation for IP addresses using ip-api.com"""
    print(f"Getting geolocation for {len(ip_list)} IP addresses...")
    
    locations = {}
    
    for i, ip in enumerate(ip_list):
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,lat,lon,query"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    locations[ip] = {
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'city': data.get('city', 'Unknown'),
                        'country': data.get('country', 'Unknown'),
                        'country_code': data.get('countryCode', 'XX'),
                        'region': data.get('regionName', '')
                    }
                    print(f"  {ip} -> {data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}")
            
            # Small delay to be respectful to the API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error getting location for {ip}: {e}")
            continue
    
    print(f"Successfully geolocated {len(locations)} IP addresses")
    return locations

def main():
    """Main execution function"""
    print("=== Canadian MP Monitor - Quick Geolocation Analytics ===")
    print(f"Started at: {datetime.now()}")
    
    # Extract top 20 IP addresses
    top_ips, total_requests = extract_top_ips_from_docker_logs(limit=20)
    
    if not top_ips:
        print("No IP addresses found in logs. Exiting.")
        return
    
    # Get geolocation data
    locations = get_geolocation_for_ips(list(top_ips.keys()))
    
    # Create analytics summary
    country_stats = defaultdict(int)
    for ip, count in top_ips.items():
        if ip in locations:
            country = locations[ip]['country']
            country_stats[country] += count
    
    # Save summary data
    summary_data = {
        'timestamp': datetime.now().isoformat(),
        'total_requests_analyzed': total_requests,
        'unique_ips_analyzed': len(top_ips),
        'top_ips': []
    }
    
    for ip, count in top_ips.items():
        ip_data = {
            'ip': ip,
            'requests': count,
            'percentage': (count / total_requests) * 100
        }
        
        if ip in locations:
            ip_data.update(locations[ip])
        
        summary_data['top_ips'].append(ip_data)
    
    # Add country summary
    summary_data['countries'] = []
    for country, count in sorted(country_stats.items(), key=lambda x: x[1], reverse=True):
        summary_data['countries'].append({
            'country': country,
            'requests': count,
            'percentage': (count / total_requests) * 100
        })
    
    # Save to file
    with open('quick_analytics.json', 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    # Print summary
    print("\n=== Quick Analytics Summary ===")
    print(f"Total requests analyzed: {total_requests:,}")
    print(f"Top {len(top_ips)} IP addresses analyzed")
    print(f"Successfully geolocated: {len(locations)} IPs")
    print(f"Countries represented: {len(country_stats)}")
    
    print(f"\nTop {min(10, len(top_ips))} visitor IPs:")
    for i, (ip, count) in enumerate(list(top_ips.items())[:10], 1):
        location_info = ""
        if ip in locations:
            loc = locations[ip]
            location_info = f" -> {loc['city']}, {loc['country']}"
        percentage = (count / total_requests) * 100
        print(f"{i:2d}. {ip:<15} {count:6,} requests ({percentage:5.1f}%){location_info}")
    
    if country_stats:
        print(f"\nTop countries:")
        for i, (country, count) in enumerate(sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:5], 1):
            percentage = (count / total_requests) * 100
            print(f"{i}. {country:<20} {count:6,} requests ({percentage:5.1f}%)")
    
    print(f"\nData saved to: quick_analytics.json")
    print(f"Completed at: {datetime.now()}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Geolocation Analytics for Canadian MP Monitor
Analyzes nginx access logs and creates a world map visualization of visitor locations.
"""

import re
import subprocess
import json
import requests
import time
from collections import defaultdict, Counter
from datetime import datetime
import folium
from folium.plugins import HeatMap
import geoip2.database
import geoip2.errors

class GeolocationAnalyzer:
    def __init__(self):
        self.ip_locations = {}
        self.ip_counts = defaultdict(int)
        self.total_requests = 0
        
    def extract_ips_from_docker_logs(self, container_name="mp-monitor-nginx", hours=24):
        """Extract IP addresses from nginx docker logs"""
        print(f"Extracting IPs from {container_name} logs (last {hours} hours)...")
        
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
            
            for line in result.stdout.split('\n'):
                match = re.match(ip_pattern, line.strip())
                if match:
                    ip = match.group(1)
                    # Skip private IP ranges
                    if not self._is_private_ip(ip):
                        ip_counts[ip] += 1
                        self.total_requests += 1
            
            print(f"Found {len(ip_counts)} unique public IP addresses from {self.total_requests} requests")
            return dict(ip_counts)
            
        except Exception as e:
            print(f"Error extracting IPs: {e}")
            return {}
    
    def _is_private_ip(self, ip):
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
    
    def get_geolocation_batch(self, ip_list, use_geoip=True):
        """Get geolocation for a batch of IP addresses"""
        print(f"Getting geolocation for {len(ip_list)} IP addresses...")
        
        locations = {}
        
        if use_geoip:
            # Try using GeoIP2 database first (more reliable)
            locations.update(self._get_geoip_locations(ip_list))
        
        # For IPs not found in GeoIP, use web API
        remaining_ips = [ip for ip in ip_list if ip not in locations]
        if remaining_ips:
            print(f"Using web API for {len(remaining_ips)} remaining IPs...")
            locations.update(self._get_web_api_locations(remaining_ips))
        
        return locations
    
    def _get_geoip_locations(self, ip_list):
        """Try to get locations using GeoIP2 database"""
        locations = {}
        
        # Try to download GeoLite2 database if not exists
        db_path = "/tmp/GeoLite2-City.mmdb"
        
        try:
            if not self._ensure_geoip_db(db_path):
                print("GeoIP database not available, skipping...")
                return locations
                
            with geoip2.database.Reader(db_path) as reader:
                for ip in ip_list:
                    try:
                        response = reader.city(ip)
                        locations[ip] = {
                            'lat': float(response.location.latitude) if response.location.latitude else None,
                            'lon': float(response.location.longitude) if response.location.longitude else None,
                            'city': response.city.name or 'Unknown',
                            'country': response.country.name or 'Unknown',
                            'country_code': response.country.iso_code or 'XX'
                        }
                    except (geoip2.errors.AddressNotFoundError, geoip2.errors.GeoIP2Error):
                        continue
                        
        except Exception as e:
            print(f"Error using GeoIP database: {e}")
        
        print(f"GeoIP resolved {len(locations)} locations")
        return locations
    
    def _ensure_geoip_db(self, db_path):
        """Download GeoLite2 database if needed"""
        import os
        
        if os.path.exists(db_path):
            return True
            
        # Note: This requires a MaxMind license key for the official database
        # For production use, you'd need to register at maxmind.com
        # For now, we'll skip this and use the web API
        return False
    
    def _get_web_api_locations(self, ip_list):
        """Get locations using free web API with rate limiting"""
        locations = {}
        
        # Use ip-api.com (free tier: 45 requests per minute)
        for i, ip in enumerate(ip_list):
            try:
                if i > 0 and i % 45 == 0:
                    print("Rate limiting: waiting 60 seconds...")
                    time.sleep(60)
                
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
                
                # Small delay to be respectful
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error getting location for {ip}: {e}")
                continue
        
        print(f"Web API resolved {len(locations)} locations")
        return locations
    
    def create_world_map(self, ip_counts, locations, output_file="visitor_map.html"):
        """Create an interactive world map with visitor locations"""
        print("Creating world map visualization...")
        
        # Create base map centered on North America (since it's a Canadian site)
        m = folium.Map(location=[45.0, -75.0], zoom_start=3)
        
        # Prepare data for visualization
        heat_data = []
        marker_data = []
        country_stats = defaultdict(int)
        
        for ip, count in ip_counts.items():
            if ip in locations:
                loc = locations[ip]
                if loc['lat'] and loc['lon']:
                    # Add to heat map (with weight based on request count)
                    heat_data.append([loc['lat'], loc['lon'], count])
                    
                    # Collect country statistics
                    country_stats[loc['country']] += count
                    
                    # Add marker for high-traffic IPs
                    if count >= 10:  # Only show markers for IPs with 10+ requests
                        popup_text = f"""
                        <b>IP:</b> {ip}<br>
                        <b>Location:</b> {loc['city']}, {loc['country']}<br>
                        <b>Requests:</b> {count:,}<br>
                        <b>% of Total:</b> {(count/self.total_requests)*100:.1f}%
                        """
                        
                        # Color code by request volume
                        if count >= 1000:
                            color = 'red'
                            radius = 15
                        elif count >= 100:
                            color = 'orange' 
                            radius = 12
                        elif count >= 50:
                            color = 'yellow'
                            radius = 10
                        else:
                            color = 'green'
                            radius = 8
                        
                        folium.CircleMarker(
                            location=[loc['lat'], loc['lon']],
                            radius=radius,
                            popup=folium.Popup(popup_text, max_width=300),
                            color='black',
                            fillColor=color,
                            fillOpacity=0.7,
                            weight=2
                        ).add_to(m)
        
        # Add heat map layer
        if heat_data:
            HeatMap(heat_data, radius=20, blur=15, max_zoom=1).add_to(m)
        
        # Add statistics to map
        stats_html = self._generate_stats_html(country_stats, len(locations))
        folium.Element(stats_html).add_to(m.get_root().html)
        
        # Save map
        m.save(output_file)
        print(f"Map saved to {output_file}")
        
        return m, country_stats
    
    def _generate_stats_html(self, country_stats, total_ips):
        """Generate HTML statistics for the map"""
        # Top 10 countries by requests
        top_countries = sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        stats_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 300px; height: auto;
                    background-color: white; border: 2px solid grey; z-index:9999;
                    font-size: 14px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
            <h4 style="margin: 0 0 10px 0;">MP Tracker Analytics</h4>
            <p style="margin: 5px 0;"><b>Total Requests:</b> {self.total_requests:,}</p>
            <p style="margin: 5px 0;"><b>Unique IPs:</b> {total_ips:,}</p>
            <p style="margin: 5px 0;"><b>Time Period:</b> Last 24 hours</p>
            
            <h5 style="margin: 10px 0 5px 0;">Top Countries:</h5>
            <div style="font-size: 12px;">
        """
        
        for country, count in top_countries:
            percentage = (count / self.total_requests) * 100
            stats_html += f"<div>{country}: {count:,} ({percentage:.1f}%)</div>"
        
        stats_html += """
            </div>
            <div style="margin-top: 10px; font-size: 11px; color: #666;">
                🔴 1000+ requests<br>
                🟠 100+ requests<br>  
                🟡 50+ requests<br>
                🟢 10+ requests
            </div>
        </div>
        """
        
        return stats_html
    
    def save_analytics_data(self, ip_counts, locations, output_file="analytics_data.json"):
        """Save analytics data to JSON file"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_requests': self.total_requests,
            'unique_ips': len(ip_counts),
            'ip_data': []
        }
        
        for ip, count in ip_counts.items():
            ip_data = {
                'ip': ip,
                'requests': count,
                'percentage': (count / self.total_requests) * 100
            }
            
            if ip in locations:
                ip_data.update(locations[ip])
            
            data['ip_data'].append(ip_data)
        
        # Sort by request count
        data['ip_data'].sort(key=lambda x: x['requests'], reverse=True)
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Analytics data saved to {output_file}")
        return data

def main():
    """Main execution function"""
    print("=== Canadian MP Monitor - Geolocation Analytics ===")
    print(f"Started at: {datetime.now()}")
    
    analyzer = GeolocationAnalyzer()
    
    # Extract IP addresses from nginx logs
    ip_counts = analyzer.extract_ips_from_docker_logs()
    
    if not ip_counts:
        print("No IP addresses found in logs. Exiting.")
        return
    
    # Get top IPs (limit to avoid API rate limits)
    top_ips = dict(sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:200])
    print(f"Analyzing top {len(top_ips)} IP addresses...")
    
    # Get geolocation data
    locations = analyzer.get_geolocation_batch(list(top_ips.keys()))
    
    # Create world map
    world_map, country_stats = analyzer.create_world_map(top_ips, locations)
    
    # Save analytics data
    analytics_data = analyzer.save_analytics_data(ip_counts, locations)
    
    # Print summary
    print("\n=== Analytics Summary ===")
    print(f"Total requests analyzed: {analyzer.total_requests:,}")
    print(f"Unique IP addresses: {len(ip_counts):,}")
    print(f"IPs with geolocation: {len(locations):,}")
    print(f"Countries represented: {len(set(loc.get('country', 'Unknown') for loc in locations.values())):,}")
    
    print("\nTop 10 visitor countries:")
    top_countries = sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (country, count) in enumerate(top_countries, 1):
        percentage = (count / analyzer.total_requests) * 100
        print(f"{i:2d}. {country:<20} {count:6,} requests ({percentage:5.1f}%)")
    
    print(f"\nMap saved as: visitor_map.html")
    print(f"Data saved as: analytics_data.json")
    print(f"Completed at: {datetime.now()}")

if __name__ == "__main__":
    main()
# Canadian MP Monitor

A web application for tracking Canadian Members of Parliament and their voting records, built with React frontend and Flask backend.

## Overview

This project monitors Canadian MPs by fetching data from the Open Parliament API, providing a searchable interface to view MP profiles and detailed voting records. The backend implements intelligent caching to optimize API performance and reduce load times.

## Architecture

### Backend (Flask)
- **Main Application**: `backend/app.py`
  - Flask API server with CORS support
  - Intelligent multi-level caching system (in-memory + file-based)
  - Background data fetching with threading
  - Serves cached MP data, voting records, and vote details

- **Cache Management**: 
  - `backend/update_cache.py` - Standalone script for updating all caches
  - `backend/check_cache.py` - Cache status monitoring utility
  - `backend/setup_cron.sh` - Automated cache update scheduling
  - Cache files stored in `backend/cache/` directory

### Frontend (React)
- **Main App**: `frontend/src/App.js` - React Router setup with three main routes
- **Components**:
  - `MPList.js` - Searchable grid of all MPs with filtering
  - `MPDetail.js` - Individual MP profile with voting history
  - `VoteDetails.js` - Detailed vote analysis with party statistics and visualization

## Key Features

### Backend Features
- **Smart Caching**: 1-hour cache duration with background refresh
- **Progressive Loading**: MPs load individually as requested, with background caching for popular MPs
- **Error Handling**: Graceful fallbacks when API calls fail
- **Performance Optimization**: Concurrent API requests with ThreadPoolExecutor
- **Persistent Storage**: JSON file caching survives server restarts

### Frontend Features
- **Real-time Search**: Filter MPs by name, riding, province, or party
- **Rich MP Profiles**: Photos, party affiliation, riding information
- **Interactive Vote History**: Click any vote to see detailed breakdown
- **Visual Vote Analysis**: Color-coded party statistics and MP vote visualization
- **Responsive Design**: Grid layouts that adapt to screen size

## API Endpoints

### Core Endpoints
- `GET /` - Backend status and cache information
- `GET /api/politicians` - Paginated MP list with search capability
- `GET /api/politicians/<path>` - Individual MP details
- `GET /api/politician/<slug>/votes` - MP's voting records (cached)
- `GET /api/votes` - Recent parliamentary votes
- `GET /api/votes/<id>/details` - Detailed vote analysis with party breakdown
- `GET /api/votes/ballots` - Individual MP votes for specific motions

### Data Sources
- **Open Parliament API**: `https://api.openparliament.ca`
- **Image Assets**: `https://openparliament.ca` (MP headshots)

## Development Setup

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

### Cache Management
```bash
# Setup automated cache updates (runs every 2 hours)
cd backend && ./setup_cron.sh

# Manual cache update
python3 update_cache.py

# Check cache status
python3 check_cache.py
```

## Dependencies

### Backend (`requirements.txt`)
- `flask==3.1.1` - Web framework
- `flask-cors==6.0.0` - Cross-origin resource sharing
- `requests==2.31.0` - HTTP client for API calls

### Frontend (`package.json`)
- `react==19.1.0` - UI framework
- `react-dom==19.1.0` - DOM rendering
- `react-router-dom==7.6.2` - Client-side routing
- `react-scripts==5.0.1` - Build tooling

## Performance Optimizations

### Caching Strategy
1. **Politicians Cache**: All MPs loaded once, cached for 1 hour
2. **Votes Cache**: Recent 100 votes cached, refreshed hourly  
3. **MP Votes Cache**: Individual MP voting records cached on-demand
4. **Background Processing**: Popular MPs pre-cached automatically

### API Rate Limiting
- Batch processing with 5-vote chunks
- 0.1-0.5 second delays between API calls
- ThreadPoolExecutor with max 3 workers
- Graceful fallbacks when API limits hit

## File Structure

```
/politics/
├── backend/
│   ├── app.py              # Main Flask application
│   ├── update_cache.py     # Cache update script
│   ├── check_cache.py      # Cache monitoring
│   ├── setup_cron.sh       # Cron job setup
│   ├── requirements.txt    # Python dependencies
│   └── cache/              # Cached data files
│       ├── politicians.json
│       ├── votes.json
│       └── mp_votes/       # Individual MP vote caches
├── frontend/
│   ├── src/
│   │   ├── App.js          # Main React app
│   │   ├── components/     # React components
│   │   └── services/       # API service layer
│   └── package.json        # Node dependencies
```

## Common Tasks

### Running the Application
```bash
# Start backend (from backend/)
python app.py

# Start frontend (from frontend/) 
npm start
```

### Cache Operations
```bash
# Force cache refresh
python3 backend/update_cache.py

# Monitor cache status
python3 backend/check_cache.py

# View cache update logs
tail -f backend/cache_update.log
```

### Testing
```bash
# Frontend tests
cd frontend && npm test

# Backend testing
cd backend && python -m pytest  # (no tests currently implemented)
```

## Error Handling

The application handles various error conditions:
- **API Unavailable**: Serves cached data when possible
- **Network Issues**: Graceful fallbacks with user feedback
- **Missing Data**: Clear error messages and retry options
- **Cache Corruption**: Automatic cache rebuilding

## Configuration

### Cache Settings (configurable in `app.py`)
- `CACHE_DURATION = 3600` # 1 hour cache lifetime
- `MP_LIMIT = 50` # Number of MPs to pre-cache
- `VOTE_LIMIT = 20` # Votes per MP to cache

### API Configuration
- Base URL: `https://api.openparliament.ca`
- User Agent: `MP-Monitor-App/1.0`
- Timeout: 30 seconds for most requests

## Production Deployment

### Server Information
- **Domain**: `https://mptracker.ca`
- **Server**: DigitalOcean droplet at `143.198.42.59`
- **Deployment**: Docker-based containerized application
- **Cache Location**: `/home/root/mp-monitor/backend/cache/` on server

### Server Cache Status (as of 2025-06-07)
The production server has a fully populated cache with:
- **Politicians Cache**: `politicians.json` (127KB, updated 15:41)
- **Votes Cache**: `votes.json` (282KB, updated 15:41) 
- **MP Votes Cache**: `mp_votes/` directory with individual MP files
  - Contains 2,522+ voting records per MP (e.g., `ziad-aboultaif.json` = 1.5MB)
  - Updated: 2025-06-07 15:49
- **Vote Details Cache**: `vote_details/` directory with comprehensive vote data
- **Vote Cache Index**: `vote_cache_index.json` (474KB) for fallback lookups
- **Historical MPs**: `historical_mps.json` (873KB) for past parliamentarians

### Cache Files Structure on Server
```
/home/root/mp-monitor/backend/cache/
├── politicians.json           # Current MPs
├── votes.json                # Recent parliamentary votes  
├── vote_cache_index.json     # Index for vote detail lookups
├── historical_mps.json       # MPs from previous sessions
├── mp_voting_statistics.json # Cache generation stats
├── mp_votes/                 # Individual MP voting records
│   ├── ziad-aboultaif.json  # 2,522 votes, 1.5MB
│   └── [other-mp-slug].json
└── vote_details/             # Detailed vote information
    ├── _votes_44-1_1_.json
    └── [other vote files]
```

### Known Issues
- **Intermittent MP Vote Loading**: Some MPs (e.g., Ziad Aboultaif) show `total_cached: 0` in API responses despite having populated cache files on server
- **Docker Cache Mismatch**: Flask app running in Docker container may not be accessing the correct cache directory
- **Cache Directory Mapping**: Potential volume mount issue between host cache (`/home/root/mp-monitor/backend/cache/`) and container cache path

### Server Management
Use Ansible for server operations:
```bash
# Access server cache
ansible mptracker -i ansible/inventory.yml -m shell -a "ls -la /home/root/mp-monitor/backend/cache/"

# Check running processes
ansible mptracker -i ansible/inventory.yml -m shell -a "ps aux | grep python"
```
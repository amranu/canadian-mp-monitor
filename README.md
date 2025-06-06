# Canadian MP Monitor

A high-performance web application for tracking Canadian Members of Parliament and their voting records. Built with React frontend and Flask backend, featuring comprehensive caching for instant data access.

## 📊 Architecture

### Frontend (React)
- Modern React with hooks and routing
- Responsive design with intuitive navigation  
- Real-time loading indicators and pagination
- Visual vote representations and party breakdowns

### Backend (Flask)
- **Cache-First Architecture**: Serves data instantly from pre-cached files
- **Smart Fallback**: API integration for new votes not yet cached
- **Historical Integration**: Seamless handling of current and previous parliament data
- **Concurrent Processing**: Multi-threaded vote enrichment and caching

### Caching System
```
├── cache_all_votes.py      # Pre-cache all parliamentary votes (4,485+)
├── incremental_update.py   # Smart 30-minute updates (new votes only)
├── fetch_historical_mps.py # Historical MP data for previous parliaments
└── Cache Structure:
    ├── vote_details/       # Individual vote files with complete data
    ├── historical_mps.json # 336 MPs from previous sessions
    ├── politicians.json    # 343 current MPs
    └── mp_votes/          # Individual MP voting records
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn
- cron (for automated updates)

### Quick Setup
```bash
# Clone the repository
git clone https://github.com/amranu/canadian-mp-monitor.git
cd canadian-mp-monitor

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
cd ../backend
```

### Initial Data Setup
```bash
# Step 1: Cache all parliamentary votes (takes ~30 minutes)
python3 cache_all_votes.py

# Step 2: Fetch historical MP data (takes ~5 minutes)
python3 fetch_historical_mps.py

# Step 3: Generate MP voting records (takes ~15 seconds)
python3 cache_mp_voting_records.py

# Step 4: Set up automated updates (requires cron)
chmod +x setup_cron.sh
./setup_cron.sh
```

### Alternative: Quick Start with Incremental Data
```bash
# For faster initial setup, start with recent data only
python3 incremental_update.py

# Then run full cache population in background
nohup python3 cache_all_votes.py > cache_setup.log 2>&1 &
```

## 🚀 Running the Application

### Start Backend
```bash
cd backend
source venv/bin/activate
python3 app.py
```
Backend runs on `http://localhost:5000`

### Start Frontend
```bash
cd frontend
npm start
```
Frontend runs on `http://localhost:3000`

## 📋 API Endpoints

| Endpoint | Description | Cache Status |
|----------|-------------|--------------|
| `GET /api/politicians` | List all MPs with pagination | Cached (3 hours) |
| `GET /api/politician/{slug}/votes` | MP voting records with pagination | Cached + Live API |
| `GET /api/votes/{id}/details` | Complete vote details with ballots | **Instant Cache** |
| `GET /api/votes` | Recent parliamentary votes | Cached (3 hours) |
| `POST /api/reload-historical-mps` | Refresh historical MP data | Admin |

## 🔄 Automated Updates

The system uses an intelligent update strategy:

### Incremental Updates (Every 30 minutes)
```bash
# Checks for new votes only - completes in <1 second
python3 incremental_update.py
```

### Full Cache Rebuild (Weekly)
```bash
# Complete refresh on Sundays at 2 AM
python3 cache_all_votes.py
```

### Cron Schedule
```bash
# View current schedule
crontab -l

# Manual setup
./setup_cron.sh
```

## 📁 Project Structure

```
canadian-mp-monitor/
├── frontend/                  # React application
│   ├── src/
│   │   ├── components/       # MP lists, vote details, etc.
│   │   ├── services/         # API integration with caching
│   │   └── ...
│   └── package.json
├── backend/                   # Flask API server
│   ├── app.py               # Main Flask application
│   ├── cache_all_votes.py   # Comprehensive vote caching
│   ├── incremental_update.py # Smart incremental updates
│   ├── fetch_historical_mps.py # Historical data fetching
│   ├── setup_cron.sh        # Automated update setup
│   └── requirements.txt
├── CLAUDE.md                # Detailed technical documentation
└── README.md               # This file
```

## 🎯 Usage Examples

### View MP Voting Record
1. Navigate to the MP list
2. Search or browse to find your MP
3. Click to view their complete voting history
4. Use "Load More" for pagination beyond cached votes

### Analyze Specific Vote
1. Click any vote from MP details or vote list
2. View complete party breakdowns and statistics  
3. See individual MP positions with visual representation
4. Historical votes show context from previous parliaments

### Track New Legislation
- New votes automatically appear every 30 minutes
- Bill information prominently displayed
- Real-time party position analysis

## 🔧 Configuration

### Cache Settings (backend/app.py)
```python
CACHE_DURATION = 10800  # 3 hours
```

### Update Frequency (setup_cron.sh)
```bash
# Incremental updates every 30 minutes
INCREMENTAL_CRON="*/30 * * * *"

# Full rebuild weekly  
FULL_CACHE_CRON="0 2 * * 0"
```

## 📊 Data Sources

- **Parliament of Canada API**: https://api.openparliament.ca
- **Current Parliament**: Session 45-1 (2025)
- **Historical Data**: Session 44-1 (2021-2024)
- **Update Frequency**: Real-time vote detection with 30-minute processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Notes
- Backend changes require restart for cache integration
- Frontend hot-reloads automatically during development
- Test with `python3 incremental_update.py` for cache validation

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- **Parliament of Canada** for providing open access to parliamentary data
- **OpenParliament.ca** for their excellent API infrastructure
- **Claude Code** for development assistance and optimization

## 🐛 Issues & Support

- Report issues on GitHub Issues
- Check `backend/*.log` files for troubleshooting
- Verify cache status at `http://localhost:5000/`

---

**Built with ❤️ for Canadian democracy and government transparency**
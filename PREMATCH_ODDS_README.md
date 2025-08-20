# 🎯 GoalServe Pre-Match Odds Service

A comprehensive service for fetching and storing pre-match odds from GoalServe API for multiple sports. The service automatically handles dynamic date ranges, retry logic, and organizes data by sport.

## 🚀 Features

- **Multi-Sport Support**: Fetches odds for 18 different sports
- **Dynamic Date Handling**: Automatically uses yesterday to today date range
- **Robust Error Handling**: Retry logic with exponential backoff
- **Real-time Monitoring**: Web interface and API endpoints for monitoring
- **Automatic File Organization**: Saves JSON files organized by sport
- **Service Management**: Start/stop/restart functionality
- **Statistics Tracking**: Comprehensive logging and statistics

## 🏆 Supported Sports

| Sport | Icon | Category | Display Name |
|-------|------|----------|--------------|
| Soccer | ⚽ | soccer_10 | Soccer |
| Basketball | 🏀 | basket_10 | Basketball |
| Tennis | 🎾 | tennis_10 | Tennis |
| Hockey | 🏒 | hockey_10 | Hockey |
| Handball | 🤾 | handball_10 | Handball |
| Volleyball | 🏐 | volleyball_10 | Volleyball |
| American Football | 🏈 | football_10 | American Football |
| Baseball | ⚾ | baseball_10 | Baseball |
| Cricket | 🏏 | cricket_10 | Cricket |
| Rugby Union | 🏉 | rugby_10 | Rugby Union |
| Rugby League | 🏉 | rugbyleague_10 | Rugby League |
| Boxing | 🥊 | boxing_10 | Boxing |
| Esports | 🎮 | esports_10 | Esports |
| Futsal | ⚽ | futsal_10 | Futsal |
| MMA | 🥋 | mma_10 | MMA |
| Table Tennis | 🏓 | table_tennis_10 | Table Tennis |
| Golf | ⛳ | golf_10 | Golf |
| Darts | 🎯 | darts_10 | Darts |

## 📁 File Structure

```
C:/Users/user/Downloads/GoalServe/Sports Pre Match/
├── soccer/
│   ├── soccer_odds_20241201_143022.json
│   └── soccer_odds_20241201_143352.json
├── basketball/
│   ├── basketball_odds_20241201_143023.json
│   └── basketball_odds_20241201_143353.json
├── tennis/
│   └── tennis_odds_20241201_143024.json
└── ... (other sports)
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.7+
- Required packages (install via `pip install -r requirements.txt`):
  - `requests`
  - `flask`
  - `flask-cors`

### Quick Start

1. **Test the service**:
   ```bash
   python run_prematch_odds.py --test
   ```

2. **Run a single fetch**:
   ```bash
   python run_prematch_odds.py --once
   ```

3. **Start continuous service**:
   ```bash
   python run_prematch_odds.py
   ```

## 📖 Usage

### Command Line Interface

```bash
# Test mode - verify configuration and test single fetch
python run_prematch_odds.py --test

# Single fetch for all sports
python run_prematch_odds.py --once

# Single fetch for specific sport
python run_prematch_odds.py --once --sport soccer

# Continuous service with custom folder
python run_prematch_odds.py --folder "C:/Custom/Path"

# Help
python run_prematch_odds.py --help
```

### API Endpoints

When running with the main application, the following API endpoints are available:

#### Service Management
- `GET /api/prematch-odds/status` - Get service status
- `POST /api/prematch-odds/start` - Start the service
- `POST /api/prematch-odds/stop` - Stop the service
- `POST /api/prematch-odds/fetch-now` - Trigger immediate fetch

#### Data Access
- `GET /api/prematch-odds/sports` - List configured sports
- `GET /api/prematch-odds/files` - Get recent files
- `GET /api/prematch-odds/test-url/<sport>` - Test URL for sport

#### Example API Usage

```bash
# Get service status
curl http://localhost:5000/api/prematch-odds/status

# Start service
curl -X POST http://localhost:5000/api/prematch-odds/start

# Fetch now
curl -X POST http://localhost:5000/api/prematch-odds/fetch-now

# Get recent files
curl http://localhost:5000/api/prematch-odds/files?limit=10
```

### Web Interface

Access the web interface at: `http://localhost:5000/prematch-odds.html`

Features:
- Real-time service status
- Start/stop controls
- Statistics dashboard
- Sports configuration display
- Recent files browser
- Auto-refresh every 10 seconds

## ⚙️ Configuration

### Service Settings

The service uses the following default settings:

- **Fetch Interval**: 30 seconds
- **Retry Delays**: 30s, 45s, 60s
- **Max Retries**: 3 per request
- **Timeout**: 10s connect, 30s read
- **Date Range**: Yesterday to Today (dynamic)

### Customization

You can modify the service behavior by editing `src/prematch_odds_service.py`:

```python
# Change fetch interval
self.fetch_interval = 60  # seconds

# Modify retry delays
self.retry_delays = [60, 90, 120]  # seconds

# Change timeout
self.timeout = (15, 45)  # (connect, read)

# Add new sports
self.sports_config['new_sport'] = {
    'category': 'new_sport_10',
    'display_name': 'New Sport',
    'icon': '🏆'
}
```

## 📊 Monitoring & Logging

### Log Levels

The service provides comprehensive logging:

- **INFO**: Normal operations, successful fetches
- **WARNING**: Timeouts, retries
- **ERROR**: Failed requests, file errors

### Statistics

The service tracks:

- Total fetches attempted
- Successful fetches
- Failed fetches
- Last fetch time
- Service running status

### Example Log Output

```
2024-12-01 14:30:22 - INFO - ✅ Base folder created/verified: C:/Users/user/Downloads/GoalServe/Sports Pre Match
2024-12-01 14:30:22 - INFO - ✅ Sport folder created/verified: C:/Users/user/Downloads/GoalServe/Sports Pre Match/soccer
2024-12-01 14:30:23 - INFO - 🔄 Fetching soccer odds (attempt 1/4)
2024-12-01 14:30:24 - INFO - ✅ Successfully fetched soccer odds
2024-12-01 14:30:24 - INFO - 💾 Saved soccer odds to C:/Users/user/Downloads/GoalServe/Sports Pre Match/soccer/soccer_odds_20241201_143024.json
```

## 🔧 Troubleshooting

### Common Issues

1. **Folder Access Denied**
   ```
   Error: Permission denied
   Solution: Ensure write permissions for the base folder
   ```

2. **Network Timeout**
   ```
   Warning: Timeout for soccer (attempt 1)
   Solution: Check internet connection, increase timeout if needed
   ```

3. **Invalid JSON Response**
   ```
   Error: JSON decode error for soccer
   Solution: Check GoalServe API status, verify access token
   ```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Test individual components:

```bash
# Test URL building
python -c "from src.prematch_odds_service import get_prematch_odds_service; s = get_prematch_odds_service(); print(s._build_odds_url('soccer', '01.12.2024', '02.12.2024'))"

# Test date calculation
python -c "from src.prematch_odds_service import get_prematch_odds_service; s = get_prematch_odds_service(); print(s._get_dynamic_dates())"
```

## 📈 Performance

### Expected Performance

- **Fetch Time**: 1-3 seconds per sport
- **File Size**: 1-50 KB per JSON file
- **Memory Usage**: ~10-50 MB
- **CPU Usage**: Minimal (mostly I/O bound)

### Optimization Tips

1. **Reduce Fetch Interval**: For real-time applications
2. **Increase Timeout**: For slow connections
3. **Selective Sports**: Fetch only needed sports
4. **File Cleanup**: Implement automatic file cleanup

## 🔒 Security Considerations

- **Access Token**: Keep your GoalServe access token secure
- **File Permissions**: Ensure proper file permissions
- **Network Security**: Use HTTPS in production
- **Rate Limiting**: Respect GoalServe API limits

## 🤝 Contributing

To add new sports or modify functionality:

1. Edit `src/prematch_odds_service.py`
2. Add sport configuration to `sports_config`
3. Test with `python run_prematch_odds.py --test`
4. Update documentation

## 📄 License

This service is part of the GoalServe Sports Betting Platform.

## 🆘 Support

For issues or questions:

1. Check the troubleshooting section
2. Review logs for error messages
3. Test with `--test` mode
4. Verify GoalServe API access

---

**Last Updated**: December 2024  
**Version**: 1.0.0  
**Compatibility**: Python 3.7+, Windows/Linux/macOS

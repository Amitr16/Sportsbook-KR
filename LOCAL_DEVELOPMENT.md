# Local Development Guide

This guide will help you run the application locally for development and debugging.

## Quick Start

### Windows
```bash
# Double-click this file or run in Command Prompt
run_local.bat

# Or use PowerShell
.\run_local.ps1
```

### Mac/Linux
```bash
# Make scripts executable
chmod +x run_local.py setup_local_db.py

# Setup and run
python setup_local_db.py
python run_local.py
```

## Manual Setup

### 1. Create Virtual Environment
```bash
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Mac/Linux
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Local Database
```bash
python setup_local_db.py
```

### 4. Run Application
```bash
python run.py
```

## What Gets Created

- **Local SQLite Database**: `local_app.db`
- **Sample Users**:
  - Superadmin: `superadmin` / `superadmin123`
  - Test User: `am1111` / `password123`
- **Sample Events**: Hiroshima Carp vs Chunichi Dragons (Baseball)

## Testing Wallet Functionality

Test the wallet balance updates locally:

```bash
python test_wallet_local.py
```

This will:
1. Place a test bet
2. Verify balance is deducted
3. Check transaction is recorded
4. Clean up test data

## Environment Variables

The application automatically detects the environment:

- **Local Development**: Uses SQLite database
- **Production**: Uses PostgreSQL (requires `DATABASE_URL`)

## Switching Between Local and Fly.io

### To run locally:
```bash
set FLASK_ENV=development  # Windows
export FLASK_ENV=development  # Mac/Linux
```

### To run on Fly.io:
```bash
set FLASK_ENV=production  # Windows
export FLASK_ENV=production  # Mac/Linux
```

## Troubleshooting

### Database Issues
- Delete `local_app.db` and run `setup_local_db.py` again
- Check if SQLite is installed: `python -c "import sqlite3; print('OK')"`

### Import Issues
- Make sure you're in the project root directory
- Check that `src/` directory exists

### Port Issues
- If port 5000 is busy, change it in `run_local.py`
- Check if another Flask app is running

## Benefits of Local Development

1. **Fast Debugging**: No deployment delays
2. **Database Access**: Direct SQLite access
3. **Logging**: Full console output
4. **Hot Reload**: Automatic restart on code changes
5. **Breakpoints**: Use your IDE's debugger

## Next Steps

Once local development is working:
1. Test wallet balance updates
2. Debug bet settlement logic
3. Test WebSocket connections
4. Fix any issues locally
5. Deploy to Fly.io when ready

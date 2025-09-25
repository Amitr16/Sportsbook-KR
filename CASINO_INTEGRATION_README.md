# Casino Integration with Sportsbook

This document describes the integration of the casino suite with the sportsbook platform to create a unified super app.

## Overview

The casino integration allows users to:
- Access casino games from the sportsbook interface
- Share the same authentication session (Google OAuth)
- Use the same wallet balance across both platforms
- Seamlessly switch between sports betting and casino games

## Architecture

### Backend Integration
- **Database**: Casino uses the same PostgreSQL database as sportsbook
- **Authentication**: Shared session-based authentication with Google OAuth
- **Wallet**: Integrated with sportsbook's `operator_wallets` table
- **API**: Casino API endpoints are served through the sportsbook Flask app

### Frontend Integration
- **Navigation**: Casino link added to sportsbook header
- **Session**: Shared session cookies for authentication
- **API Calls**: Casino frontend calls sportsbook API endpoints
- **Styling**: Consistent branding and theme

## Files Modified

### Backend Changes
1. **`casino-suite-pro/backend/config.py`**
   - Updated to use PostgreSQL instead of SQLite
   - Changed database URI to use `DATABASE_URL` environment variable

2. **`casino-suite-pro/backend/main.py`**
   - Updated to use asyncpg for PostgreSQL
   - Modified authentication to use shared session
   - Updated wallet functions to use sportsbook wallet system

3. **`src/routes/casino_api.py`** (NEW)
   - Flask blueprint for casino API endpoints
   - Integrated with sportsbook authentication and wallet
   - Simplified game logic for slots, roulette, blackjack, baccarat, crash

4. **`src/main.py`**
   - Added casino route to serve frontend
   - Registered casino API blueprint
   - Added casino link to sportsbook navigation

### Frontend Changes
1. **`casino-suite-pro/frontend/src/config.js`**
   - Updated to use sportsbook backend API
   - Changed API base URL to same origin

2. **`casino-suite-pro/frontend/src/ui/App.jsx`**
   - Updated API calls to use session authentication
   - Added sportsbook navigation link

3. **All game components** (`Slots.jsx`, `RoulettePro.jsx`, `Blackjack.jsx`, `Baccarat.jsx`, `Crash.jsx`)
   - Updated API endpoints to use `/api/casino/` prefix
   - Changed authentication to use session cookies
   - Removed hardcoded user IDs

4. **`src/static/index.html`**
   - Added casino link to authenticated user section
   - Styled casino button with golden theme

## API Endpoints

The casino integration adds the following API endpoints:

- `GET /casino` - Serve casino frontend
- `GET /api/casino/health` - Health check
- `GET /api/casino/wallet/balance` - Get user balance
- `POST /api/casino/slots/spin` - Play slots
- `POST /api/casino/roulette/spin` - Play roulette
- `POST /api/casino/blackjack/play` - Play blackjack
- `POST /api/casino/baccarat/play` - Play baccarat
- `POST /api/casino/crash/play` - Play crash
- `GET /api/casino/history` - Get game history

## Wallet Integration

The casino uses the sportsbook's wallet system:
- **Table**: `operator_wallets`
- **Wallet Type**: `bookmaker_capital` (main user balance)
- **Shared Balance**: Same balance for sports betting and casino games
- **Real-time Updates**: Balance changes immediately across both platforms

## Authentication Flow

1. User signs in to sportsbook with Google OAuth
2. Session is created and stored in Flask session
3. User clicks "🎰 Casino" button
4. Casino frontend loads with shared session
5. All casino API calls use session authentication
6. Wallet balance is shared between platforms

## Testing

Run the integration test:
```bash
python test_casino_integration.py
```

Manual testing:
1. Start the sportsbook: `python run.py`
2. Visit: `http://localhost:5000`
3. Sign in with Google
4. Click the "🎰 Casino" button
5. Play casino games with your shared wallet balance

## Environment Variables

Ensure these are set in your `.env.local`:
```bash
DATABASE_URL=postgresql://postgres:admin@localhost:5432/goalserve_sportsbook
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Dependencies

The casino integration requires:
- PostgreSQL database (shared with sportsbook)
- Flask session support
- Google OAuth credentials
- Casino frontend built and available

## Future Enhancements

- Game history storage in database
- Real-time balance updates via WebSocket
- Advanced game statistics and analytics
- Multi-currency support
- Mobile-responsive casino interface
- Live dealer games integration

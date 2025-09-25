# Casino Integration Deployment Guide for Fly.io

This guide walks you through deploying the casino-integrated sportsbook to Fly.io.

## Prerequisites

1. **Fly.io CLI installed**: `flyctl` must be installed and configured
2. **Fly.io account**: You need a Fly.io account with billing enabled
3. **PostgreSQL database**: A Fly.io PostgreSQL database attached to your app
4. **Domain configured**: Your app should have a domain configured

## Pre-Deployment Checklist

### 1. Environment Variables
- [ ] Copy `env.production.template` to `env.production`
- [ ] Fill in your actual database URL
- [ ] Update Google OAuth redirect URI to production domain
- [ ] Set your secret key
- [ ] Configure CORS origins for your domain

### 2. Database Setup
- [ ] Ensure PostgreSQL database is attached to your Fly.io app
- [ ] Verify database connection works
- [ ] Run `python create_casino_tables_fly.py` to create casino tables

### 3. Frontend Assets
- [ ] Casino frontend is built (`casino-suite-pro/frontend/dist/` exists)
- [ ] All casino assets are properly configured for multi-tenant routing

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# Run the automated deployment script
python deploy_casino_to_fly.py
```

This script will:
1. Check prerequisites
2. Build casino frontend
3. Create casino database tables
4. Deploy to Fly.io
5. Verify deployment

### Option 2: Manual Deployment

#### Step 1: Build Casino Frontend
```bash
cd casino-suite-pro/frontend
npm run build
cd ../..
```

#### Step 2: Create Casino Tables
```bash
python create_casino_tables_fly.py
```

#### Step 3: Deploy to Fly.io
```bash
flyctl deploy
```

#### Step 4: Verify Deployment
```bash
flyctl status
flyctl logs
flyctl open
```

## Post-Deployment Verification

### 1. Check Application Status
```bash
flyctl status
flyctl logs
```

### 2. Test Casino Integration
1. Open your sportsbook: `https://your-app.fly.dev`
2. Log in with Google OAuth
3. Navigate to casino section
4. Test each game:
   - **Blackjack**: Deal cards, hit/stand, check wallet updates
   - **Slots**: Spin reels, check payouts and animations
   - **Baccarat**: Place bets, check results
   - **Roulette**: Spin wheel, check betting
   - **Crash**: Play crash game

### 3. Test Multi-Tenant Routing
1. Access casino via different subdomains
2. Verify assets load correctly
3. Check that sessions are maintained

### 4. Test Database Integration
1. Play a few games
2. Check game history
3. Verify wallet updates are persistent

## Troubleshooting

### Common Issues

#### 1. Casino Assets Not Loading
**Symptoms**: 404 errors for casino assets
**Solution**: Check multi-tenant routing configuration
```bash
# Check if assets are being served correctly
curl -I https://your-app.fly.dev/casino/assets/back-BA3l7DvJ.png
```

#### 2. Database Connection Issues
**Symptoms**: 500 errors, database connection failures
**Solution**: Verify database URL and connection
```bash
# Check database connection
flyctl ssh console
python -c "from src.db_compat import get_connection; print(get_connection())"
```

#### 3. Session Not Inherited
**Symptoms**: Casino shows "Guest" user, wallet not updating
**Solution**: Check session configuration and CORS settings
```bash
# Check session cookies
flyctl logs | grep -i session
```

#### 4. Game History Blank
**Symptoms**: History shows "NO GAME HISTORY FOUND"
**Solution**: Check database tables and API endpoints
```bash
# Check if game_round table exists
flyctl ssh console
python -c "from src.db_compat import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM game_round'); print(cursor.fetchone())"
```

### Debugging Commands

```bash
# View real-time logs
flyctl logs --follow

# SSH into the container
flyctl ssh console

# Check database tables
flyctl ssh console
python -c "from src.db_compat import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('\\dt'); print(cursor.fetchall())"

# Test casino API endpoints
curl -X GET https://your-app.fly.dev/api/casino/wallet/balance
curl -X GET https://your-app.fly.dev/api/casino/user/info
```

## Database Schema

The casino integration adds these tables:

### `game_round`
- Stores individual game rounds
- Tracks stakes, payouts, and results
- Used for game history

### `casino_sessions`
- Stores active casino sessions
- Tracks game state and user data
- Used for session management

## Environment Variables

Key environment variables for production:

```bash
# Database
DATABASE_URL=postgresql://username:password@hostname:port/database

# OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=https://your-app.fly.dev/auth/google/callback

# CORS
CORS_ORIGINS=["https://your-app.fly.dev","https://your-frontend.com"]

# Security
SECRET_KEY=your_secret_key

# Casino
CASINO_ENABLED=true
CASINO_API_URL=https://your-app.fly.dev
```

## Monitoring

### Health Checks
- App health: `https://your-app.fly.dev/health`
- Casino API: `https://your-app.fly.dev/api/casino/wallet/balance`

### Logs to Monitor
- Database connection errors
- Session authentication issues
- Casino game errors
- Asset loading problems

## Rollback Plan

If deployment fails:

1. **Quick rollback**: `flyctl deploy --image previous`
2. **Database rollback**: Drop casino tables if needed
3. **Full rollback**: Revert to previous commit and redeploy

## Support

If you encounter issues:

1. Check the logs: `flyctl logs`
2. Verify database connectivity
3. Test API endpoints individually
4. Check environment variables
5. Verify frontend assets are built correctly

## Success Criteria

Deployment is successful when:

- [ ] App starts without errors
- [ ] Casino frontend loads with all assets
- [ ] User authentication works
- [ ] Wallet system functions correctly
- [ ] All casino games work properly
- [ ] Game history displays correctly
- [ ] Multi-tenant routing works
- [ ] Database operations complete successfully

# API Files Database Connection Audit

## Summary
Comprehensive audit of all API-related files that might be using database connections.

## API Files Status

### ✅ SAFE - No Database Connections:

#### 1. **casino_api.py**
- **Routes**: Casino game API endpoints
- **DB Connections**: NONE
- **Status**: ✅ Safe - No database connections used

#### 2. **public_apis.py**
- **Routes**: 
  - `/api/public/sports` - Get available sports
  - `/api/public/sports/<sport>/events` - Get events for a sport
  - `/api/public/events` - Get all events
  - `/api/public/odds/<event_id>` - Get odds for an event
- **DB Connections**: Imports `connection_ctx` but NEVER uses it
- **Status**: ✅ Safe - Only reads JSON files from filesystem, no DB queries
- **Note**: The import can be removed as it's unused

### ✅ SAFE - Uses connection_ctx Correctly:

#### 3. **clean_multitenant_routing.py**
- **Routes**: Multitenant routing and subdomain handling
- **DB Connections**: Uses `connection_ctx()` in 6 places
- **Status**: ✅ Safe - All connections properly wrapped with `connection_ctx()`
- **Examples**:
  - Line 40: Operator lookup with `connection_ctx()`
  - Line 143: Casino settings lookup with `connection_ctx()`
  - Line 516: Database connection test with `connection_ctx()`
  - Line 651: Theme customization with `connection_ctx()`
  - Line 917: Bulletproof error handling with `connection_ctx()`

### ✅ SAFE - No Database Connections:

#### 4. **websocket_service.py**
- **Type**: WebSocket/SocketIO handlers for live odds
- **Routes**: 
  - `connect` event
  - `disconnect` event
  - `subscribe_live_odds` event
  - `request_live_odds` event
- **DB Connections**: NONE
- **Status**: ✅ Safe - Only uses GoalServe API client, no database queries

## Already Audited Route Files (from main audit):

### Files with DB Connection Issues (Need Fixes):
1. **branding.py** - Uses `get_db_connection()` - Missing tracking release
2. **public_leaderboard.py** - Uses `get_db_connection()` - Missing tracking release
3. **multitenant_routing.py** - Uses `get_db_connection()` - Missing tracking release
4. **theme_customization.py** - Uses `get_db_connection()` - Missing tracking release
5. **sportsbook_registration.py** - Uses `get_db_connection()` - Missing tracking release
6. **json_sports.py** - Uses `get_db_connection()` - Missing tracking release

### Files Already Fixed:
7. **betting.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`
8. **auth.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`
9. **tenant_auth.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`
10. **bet_settlement_service.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`

## Conclusion

### API Files are NOT the Problem ✅
- **casino_api.py**: No DB usage
- **public_apis.py**: No DB usage (only filesystem reads)
- **clean_multitenant_routing.py**: Uses `connection_ctx()` correctly
- **websocket_service.py**: No DB usage

### The Real Problem is in Route Files:
The persistent connection leak issue is **NOT** coming from API files. It's coming from:

1. **Route files using `get_db_connection()` pattern** without proper tracking release
2. **Health endpoint** creating SQLAlchemy engines without disposal

### Action Items:
1. ✅ API files are clean - No action needed
2. ❌ Focus on route files listed in main README.md
3. ❌ Fix `get_db_connection()` tracking release in 6 route files
4. ❌ Fix health endpoint SQLAlchemy engine disposal

## Files Added to Audit Folder:
- `public_apis.py` - For completeness (no issues)
- `clean_multitenant_routing.py` - Example of correct `connection_ctx()` usage
- `casino_api.py` - For completeness (no DB usage)


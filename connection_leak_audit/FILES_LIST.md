# Complete File List - Connection Leak Audit

## Total Files: 33

### Documentation (2 files):
1. **README.md** - Main audit documentation with problem description and fixes
2. **API_FILES_AUDIT.md** - API-specific audit results

### Core Infrastructure (6 files):
3. **db_compat.py** - Database compatibility layer and connection pooling
4. **main.py** - Flask app initialization
5. **connection_tracker.py** - Connection tracking utility
6. **sqlalchemy_tracking.py** - SQLAlchemy connection tracking
7. **sqlalchemy_session_tracker.py** - SQLAlchemy session tracking
8. **sqlalchemy_monkey_patch.py** - Auto-track SQLAlchemy sessions

### Background Workers (1 file):
9. **bet_settlement_service.py** - ✅ FIXED - All SQLAlchemy replaced with `connection_ctx()`

### Route Files - CRITICAL (Need Fixes) (8 files):
10. **branding.py** - ❌ URGENT - Missing tracking release, most frequently called
11. **public_leaderboard.py** - ❌ HIGH - Missing tracking release
12. **multitenant_routing.py** - ❌ HIGH - Missing tracking release
13. **json_sports.py** - ❌ HIGH - Missing tracking acquisition and release
14. **theme_customization.py** - ❌ MEDIUM - Missing tracking acquisition and release
15. **theme_customization1.py** - ❌ MEDIUM - Backup file, same issues
16. **sportsbook_registration.py** - ❌ MEDIUM - Missing tracking release
17. **sportsbook_registration1.py** - ❌ MEDIUM - Backup file, same issues

### Route Files - Admin Only (Lower Priority) (6 files):
18. **comprehensive_admin.py** - ❌ LOW - Admin-only, potential leaks
19. **comprehensive_superadmin.py** - ❌ LOW - Superadmin-only, potential leaks
20. **rich_admin_interface.py** - ❌ LOW - Admin-only, potential leaks
21. **rich_superadmin_interface1.py** - ❌ LOW - Superadmin-only, potential leaks
22. **superadmin.py** - ❌ LOW - Superadmin-only, potential leaks
23. **tenant_admin.py** - ❌ LOW - Tenant admin, potential leaks

### Health Monitoring (1 file):
24. **health.py** - ❌ HIGH - Creates SQLAlchemy engines, never disposes them

### Auth Routes (2 files):
25. **auth.py** - ✅ FIXED - SQLAlchemy replaced with `connection_ctx()`
26. **tenant_auth.py** - ✅ FIXED - SQLAlchemy replaced with `connection_ctx()`

### Betting Routes (1 file):
27. **betting.py** - ✅ FIXED - All SQLAlchemy replaced with `connection_ctx()`

### Service Files (3 files):
28. **web3_operator_wallet_service.py** - ✅ SAFE - Uses `connection_ctx()` correctly
29. **web3_sync_service.py** - ✅ SAFE - Uses `connection_ctx()` correctly
30. **web3_reset_service.py** - ✅ SAFE - Uses `connection_ctx()` correctly

### API Files (3 files):
31. **public_apis.py** - ✅ SAFE - No DB connections (filesystem only)
32. **clean_multitenant_routing.py** - ✅ SAFE - Uses `connection_ctx()` correctly (example)
33. **casino_api.py** - ✅ SAFE - No DB connections

## Files Status Summary:

### ✅ SAFE/FIXED (12 files):
- bet_settlement_service.py
- auth.py
- tenant_auth.py
- betting.py
- web3_operator_wallet_service.py
- web3_sync_service.py
- web3_reset_service.py
- public_apis.py
- clean_multitenant_routing.py
- casino_api.py
- connection_tracker.py (infrastructure)
- db_compat.py (infrastructure)

### ❌ NEED FIXES (15 files):

**URGENT/HIGH Priority (9 files):**
1. branding.py (most frequently called)
2. public_leaderboard.py
3. multitenant_routing.py
4. json_sports.py
5. theme_customization.py
6. sportsbook_registration.py
7. health.py (SQLAlchemy engine disposal)
8. theme_customization1.py (backup)
9. sportsbook_registration1.py (backup)

**LOW Priority - Admin Only (6 files):**
10. comprehensive_admin.py
11. comprehensive_superadmin.py
12. rich_admin_interface.py
13. rich_superadmin_interface1.py
14. superadmin.py
15. tenant_admin.py

## Next Steps:
1. Read README.md for detailed problem description
2. Read API_FILES_AUDIT.md for API-specific findings
3. Start fixing files in priority order (URGENT → HIGH → MEDIUM → LOW)
4. Use the fix patterns documented in README.md


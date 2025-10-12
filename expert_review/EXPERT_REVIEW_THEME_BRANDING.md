# Theme & Branding Routes

## 1. Branding Cache (src/routes/branding.py)

### Current Implementation (Lines 17-60)

```python
# Aggressive branding cache for multi-tenant scalability
# Branding rarely changes - cache for 1 hour
_BRANDING_CACHE = {}
_CACHE_TTL = 3600  # 1 hour (branding changes are rare)

def _get_cached(key, loader):
    """Simple TTL cache"""
    now = time.time()
    if key in _BRANDING_CACHE:
        cached_time, cached_data = _BRANDING_CACHE[key]
        if now - cached_time < _CACHE_TTL:
            return cached_data
    
    data = loader()
    _BRANDING_CACHE[key] = (now, data)
    return data

def _load_operator_branding_from_db(subdomain):
    """Load operator branding from database"""
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cur:
                # Query operator and theme data
                cur.execute("""
                    SELECT so.id, so.sportsbook_name, so.subdomain, so.settings,
                           st.primary_color, st.secondary_color, st.accent_color,
                           st.background_color, st.text_color, st.font_family,
                           st.layout_style, st.button_style, st.card_style,
                           st.logo_type, st.logo_url, st.sportsbook_name as theme_name
                    FROM sportsbook_operators so
                    LEFT JOIN sportsbook_themes st ON so.id = st.sportsbook_operator_id
                    WHERE so.subdomain = %s AND so.is_active = true
                """, (subdomain,))
                
                result = cur.fetchone()
        
        if not result:
            return None
        
        # Build branding object
        return {
            'operator': {'id': result[0], 'name': result[1], ...},
            'theme': {'primary_color': result[4], ...}
        }
    except (PoolTimeout, OperationalError) as e:
        current_app.logger.error("DB error loading branding for %s: %s", subdomain, e)
        # Return stale cache if available
        if key in _BRANDING_CACHE:
            _, stale_data = _BRANDING_CACHE[key]
            return stale_data
        return None

def get_operator_branding(subdomain):
    """Get operator branding (with caching)"""
    return _get_cached(f"branding:{subdomain}", lambda: _load_operator_branding_from_db(subdomain))
```

## 2. Tenant Validation Cache (src/routes/clean_multitenant_routing.py)

### Current Implementation (Lines 18-59)

```python
# Tenant metadata cache for multi-tenant scalability
# Subdomain → operator mapping rarely changes (only when new operators register)
_TENANT_CACHE = {}
_TENANT_CACHE_TTL = 3600  # 1 hour

def validate_subdomain(subdomain):
    """Validate subdomain and return operator info (with aggressive caching)"""
    # Check cache first (subdomain→operator mapping rarely changes)
    cache_key = f"tenant:{subdomain}"
    now = time.time()
    
    if cache_key in _TENANT_CACHE:
        cached_time, cached_data = _TENANT_CACHE[cache_key]
        if now - cached_time < _TENANT_CACHE_TTL:
            return cached_data  # Return (operator, None) or (None, error)
    
    # Cache miss - query DB
    from src.db_compat import connection_ctx
    
    with connection_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, sportsbook_name, login, password_hash, subdomain, is_active, email
                FROM sportsbook_operators 
                WHERE subdomain = %s
            """, (subdomain,))
            operator = cur.fetchone()
    
    if not operator:
        result = (None, "Sportsbook not found")
        _TENANT_CACHE[cache_key] = (now, result)  # Cache negative results too
        return result
    
    if not operator['is_active']:
        result = (None, "This sportsbook is currently disabled")
        _TENANT_CACHE[cache_key] = (now, result)
        return result
    
    result = (dict(operator), None)
    _TENANT_CACHE[cache_key] = (now, result)  # Cache successful result
    return result
```

## 3. Public Theme Endpoint (src/routes/clean_multitenant_routing.py)

### Current Implementation (Lines 692-780)

```python
@clean_multitenant_bp.route('/<subdomain>/api/public/load-theme', methods=['GET'])
def load_public_theme_for_operator(subdomain):
    """Load theme for public use - uses cached branding (DB-free for scalability)"""
    from flask import jsonify, current_app
    from src.routes.branding import get_operator_branding
    
    # Use cached branding - NO DB HIT!
    # validate_subdomain is called internally by get_operator_branding (with cache)
    try:
        branding = get_operator_branding(subdomain)
        
        if not branding:
            current_app.logger.warning("❌ Operator not found for %s, serving defaults", subdomain)
            # Always return defaults, never 404
            return jsonify({
                'primaryColor': '#22C55E',
                'secondaryColor': '#3b82f6',
                'accentColor': '#22C55E',
                'backgroundColor': '#1A1A1A',
                'textColor': '#FFFFFF',
                'fontFamily': 'Inter, sans-serif',
                'layoutStyle': 'modern',
                'buttonStyle': 'rounded',
                'cardStyle': 'shadow',
                'logoType': 'default',
                'logoUrl': '',
                'sportsbookName': subdomain
            }), 200
        
        print(f"✅ Loaded theme for {subdomain} from cache (no DB hit)")
        
        # Extract theme from branding
        theme = branding.get('theme', {})
        operator_name = branding.get('operator', {}).get('name', subdomain)
        
        # Build response from cached data (no DB query!)
        # ... rest of function returns theme JSON
    except Exception as e:
        current_app.logger.exception("❌ load-theme crashed for %s; serving defaults", subdomain)
        # Always return defaults, never 500
        return jsonify({...defaults...}), 200
```

## 4. Theme CSS Generation (src/routes/theme_customization.py)

### Current Implementation (Lines 362-421)

```python
@theme_bp.route('/theme-css/<subdomain>', methods=['GET'])
def get_theme_css(subdomain):
    """Generate CSS for a specific operator's theme (uses cached branding)"""
    try:
        print(f"🔍 Generating theme CSS for subdomain: {subdomain}")
        
        # Use cached branding instead of querying DB
        from src.routes.branding import get_operator_branding, generate_custom_css
        branding = get_operator_branding(subdomain)
        
        if not branding:
            print(f"❌ Operator not found for subdomain: {subdomain}")
            return "/* Operator not found */", 404, {'Content-Type': 'text/css'}
        
        # Generate CSS from cached branding (no DB hit!)
        css = generate_custom_css(branding)
        
        # Extract just the CSS content (remove <style> tags)
        import re
        css_content = re.sub(r'<style>|</style>', '', css).strip()
        
        # Return the CSS directly (skip all DB queries)
        print(f"✅ Generated theme CSS from cache (no DB hit)")
        return css_content, 200, {'Content-Type': 'text/css'}
        
    except Exception as e:
        print(f"Error generating theme CSS: {e}")
        return "/* Error generating CSS */", 500, {'Content-Type': 'text/css'}
```

## Questions for Expert:

1. **In-process cache**: Should I replace `_BRANDING_CACHE` dict with Redis immediately, or is in-process OK for Phase 1?
2. **Cache invalidation**: How should I invalidate cache when admin updates branding?
3. **Stale cache fallback**: Is my current implementation safe for production?
4. **Theme CSS**: Is generating CSS on-the-fly from cache OK, or should I pre-render and store?


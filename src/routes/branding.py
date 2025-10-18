"""
Comprehensive branding and customization system for sportsbook operators
"""

from flask import Blueprint, request, jsonify, render_template_string, current_app
from src.db_compat import connection_ctx
from psycopg_pool.errors import PoolTimeout
from psycopg.errors import OperationalError
import json
import os
from datetime import datetime
import time
import logging

branding_bp = Blueprint('branding', __name__)

# Two-tier cache: Redis (distributed) + in-process (fallback)
# Branding rarely changes - cache for 1 hour
_BRANDING_CACHE = {}  # In-process fallback cache
_CACHE_TTL = 3600  # 1 hour (branding changes are rare)

def _get_cached(key, loader):
    """
    Two-tier cache: Redis (distributed) + in-process (fallback)
    1. Try Redis first (shared across all instances)
    2. Fall back to in-process cache
    3. If both miss, call loader and populate both caches
    """
    from src.utils.redis_cache import redis_cache_get, redis_cache_set
    
    # Tier 1: Try Redis (distributed cache)
    redis_value = redis_cache_get(key)
    if redis_value is not None:
        # Also update in-process cache for faster subsequent access
        _BRANDING_CACHE[key] = (time.time(), redis_value)
        return redis_value
    
    # Tier 2: Try in-process cache
    now = time.time()
    if key in _BRANDING_CACHE:
        cached_time, cached_data = _BRANDING_CACHE[key]
        if now - cached_time < _CACHE_TTL:
            # Warm Redis cache from in-process cache
            redis_cache_set(key, cached_data, _CACHE_TTL)
            return cached_data
    
    # Both caches miss - load from DB
    data = loader()
    
    # Populate both caches
    _BRANDING_CACHE[key] = (now, data)
    redis_cache_set(key, data, _CACHE_TTL)
    
    return data

def get_db_connection():
    """
    LEGACY FUNCTION - Returns pooled connection that MUST be closed by caller.
    Prefer using connection_ctx() context manager in new code.
    """
    from src.utils.connection_tracker import track_connection_acquired
    import time
    from src.db_compat import connect
    from pathlib import Path
    # Use connect() which returns a connection with _pool attached
    # Caller must call conn.close() to return to pool
    # Track this connection acquisition
    context, track_start = track_connection_acquired(f"{Path(__file__).name}::get_db_connection")
    conn = connect(use_pool=True)
    conn._tracking_context = context
    conn._tracking_start = track_start
    return conn

def _load_operator_branding_from_db(subdomain):
    """Load operator branding from database (not cached) — one fast query, then release the connection."""
    from src.db_compat import connection_ctx
    try:
        with connection_ctx(timeout=5) as conn:
            # keep this request short; avoid holding the slot
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '1500ms'")
                cur.execute(
                    """
                    SELECT id, sportsbook_name, subdomain, email, is_active,
                           settings, created_at
                    FROM sportsbook_operators
                    WHERE subdomain = %s AND is_active = TRUE
                    """,
                    (subdomain,),
                )
                row = cur.fetchone()
        if not row:
            return None
        # Return a plain, JSON-safe dict so caching & downstream never hold DB objects
        return {
            "id": row.get("id"),
            "sportsbook_name": row.get("sportsbook_name"),
            "subdomain": row.get("subdomain"),
            "email": row.get("email"),
            "is_active": row.get("is_active"),
            "settings": row.get("settings"),
            "created_at": row.get("created_at"),
        }
    except Exception as e:
        logging.error(f"❌ Database error loading operator branding for {subdomain}: {e}")
        return None

def get_operator_branding_cached_only(subdomain):
    """
    Return cached branding if present; otherwise None (NEVER hits DB)
    Checks both Redis and in-process cache
    Use this for public/high-traffic endpoints to guarantee DB-free operation
    """
    from src.utils.redis_cache import redis_cache_get
    
    key = f"branding:{subdomain}"
    
    # Try Redis first (distributed cache)
    redis_value = redis_cache_get(key)
    if redis_value is not None:
        return redis_value
    
    # Fall back to in-process cache
    now = time.time()
    if key in _BRANDING_CACHE:
        cached_time, cached_data = _BRANDING_CACHE[key]
        if now - cached_time < _CACHE_TTL:
            return cached_data
    
    return None

def get_operator_branding(subdomain):
    """Get operator branding and customization settings (cached)
    
    Degrades gracefully on DB pool exhaustion by serving cached/default values.
    """
    cache_key = f"branding:{subdomain}"
    operator = None
    
    try:
        # Try to load from cache or DB
        operator = _get_cached(cache_key, lambda: _load_operator_branding_from_db(subdomain))
    except (PoolTimeout, OperationalError) as e:
        # DB unavailable - serve stale cache if present, otherwise return None
        logging.warning(f"⚠️ Branding DB unavailable ({type(e).__name__}). Serving cached/default for {subdomain}")
        if cache_key in _BRANDING_CACHE:
            _, operator = _BRANDING_CACHE[cache_key]
            logging.info(f"✅ Serving stale cache for {subdomain}")
    except Exception as e:
        logging.error(f"❌ Unexpected error loading branding for {subdomain}: {e}")
    
    if not operator:
        return None
    
    # Parse settings or use defaults
    settings = json.loads(operator.get('settings') or "{}")
    
    # Default branding settings
    default_branding = {
        'theme': {
            'primary_color': '#f39c12',
            'secondary_color': '#2c3e50',
            'accent_color': '#e74c3c',
            'background_color': '#1a1a1a',
            'text_color': '#ffffff',
            'card_background': '#2d3748',
            'success_color': '#27ae60',
            'warning_color': '#f39c12',
            'error_color': '#e74c3c'
        },
        'branding': {
            'logo_url': '',
            'favicon_url': '',
            'welcome_message': f'Welcome to {operator.get("sportsbook_name", "Sports King")}',
            'footer_text': f'© 2025 {operator.get("sportsbook_name", "Sports King")}. All rights reserved.',
            'contact_email': operator.get('email', 'support@sportsbook.com'),
            'support_phone': '',
            'social_links': {
                'facebook': '',
                'twitter': '',
                'instagram': '',
                'telegram': ''
            }
        },
        'features': {
            'live_betting': True,
            'cash_out': True,
            'multi_bet': True,
            'live_streaming': False,
            'statistics': True,
            'promotions': True
        },
        'betting': {
            'default_currency': 'USD',
            'currency_symbol': '$',
            'odds_format': 'decimal',  # decimal, fractional, american
            'min_bet': 1.0,
            'max_bet': 10000.0,
            'max_payout': 100000.0,
            'commission_rate': 0.05
        },
        'layout': {
            'show_promotions_banner': True,
            'show_live_scores': True,
            'show_trending_events': True,
            'sidebar_position': 'left',  # left, right
            'compact_mode': False
        }
    }
    
    # Merge with operator's custom settings
    branding = default_branding.copy()
    if 'branding' in settings:
        branding.update(settings['branding'])
    
    # Add operator info
    # Normalize created_at to ISO, whether datetime or string
    created_at = operator.get("created_at")
    if created_at is not None:
        try:
            from datetime import datetime, date
            if isinstance(created_at, (datetime, date)):
                created_at = created_at.isoformat()
            else:
                s = str(created_at)
                if s.endswith("Z"):
                    s = s.replace("Z", "+00:00")
                created_at = datetime.fromisoformat(s).isoformat()
        except Exception:
            created_at = str(created_at)
    
    branding['operator'] = {
        'id': operator.get('id', 0),
        'name': operator.get('sportsbook_name', 'Sports King'),
        'subdomain': operator.get('subdomain', subdomain),
        'email': operator.get('email', 'support@sportsbook.com'),
        'created_at': created_at
    }
    
    return branding

def generate_custom_css(branding):
    """Generate custom CSS based on operator branding"""
    theme = branding.get('theme', {})
    
    css = f"""
    <style>
    :root {{
        --primary-color: {theme.get('primary_color', '#f39c12')};
        --secondary-color: {theme.get('secondary_color', '#2c3e50')};
        --accent-color: {theme.get('accent_color', '#e74c3c')};
        --background-color: {theme.get('background_color', '#1a1a1a')};
        --text-color: {theme.get('text_color', '#ffffff')};
        --card-background: {theme.get('card_background', '#2d3748')};
        --success-color: {theme.get('success_color', '#27ae60')};
        --warning-color: {theme.get('warning_color', '#f39c12')};
        --error-color: {theme.get('error_color', '#e74c3c')};
    }}
    
    /* Override default colors */
    body {{
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
    }}
    
    .navbar {{
        background-color: var(--secondary-color) !important;
    }}
    
    .btn-primary {{
        background-color: var(--primary-color) !important;
        border-color: var(--primary-color) !important;
    }}
    
    .btn-primary:hover {{
        background-color: var(--accent-color) !important;
        border-color: var(--accent-color) !important;
    }}
    
    .card {{
        background-color: var(--card-background) !important;
        border-color: var(--secondary-color) !important;
    }}
    
    .odds-button {{
        background-color: var(--primary-color) !important;
        color: white !important;
    }}
    
    .odds-button:hover {{
        background-color: var(--accent-color) !important;
    }}
    
    .text-success {{
        color: var(--success-color) !important;
    }}
    
    .text-warning {{
        color: var(--warning-color) !important;
    }}
    
    .text-danger {{
        color: var(--error-color) !important;
    }}
    
    /* Custom branding elements */
    .brand-logo {{
        max-height: 40px;
        width: auto;
    }}
    
    .welcome-banner {{
        background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
    }}
    
    .footer-custom {{
        background-color: var(--secondary-color);
        color: var(--text-color);
        padding: 20px 0;
        margin-top: 40px;
    }}
    
    .social-links a {{
        color: var(--primary-color);
        margin: 0 10px;
        font-size: 1.2em;
    }}
    
    .social-links a:hover {{
        color: var(--accent-color);
    }}
    
    /* ================================================
       MOBILE-RESPONSIVE STYLES
       ================================================ */
    
    /* Touch-friendly buttons - larger tap targets on mobile */
    @media (max-width: 768px) {{
        .btn, button, .odds-button {{
            min-height: 44px !important;
            padding: 12px 16px !important;
            font-size: 16px !important;
        }}
        
        /* Larger tap targets for links */
        a {{
            padding: 4px 0 !important;
        }}
        
        /* Mobile-friendly forms */
        input, select, textarea {{
            font-size: 16px !important;
            min-height: 44px !important;
            padding: 12px !important;
        }}
    }}
    
    /* Responsive layout adjustments */
    @media (max-width: 768px) {{
        /* Hide or adjust navbar for mobile */
        .navbar {{
            padding: 0.5rem 1rem !important;
        }}
        
        .navbar-brand {{
            font-size: 1.2rem !important;
        }}
        
        .navbar-nav {{
            margin-top: 0.5rem;
        }}
        
        .navbar-nav .nav-link {{
            padding: 0.75rem 1rem !important;
        }}
        
        /* Stack containers vertically */
        .container, .container-fluid {{
            padding-left: 15px !important;
            padding-right: 15px !important;
        }}
        
        /* Full width cards on mobile */
        .card {{
            margin-bottom: 1rem !important;
        }}
        
        /* Responsive grid - stack columns */
        .row > [class*='col-'] {{
            margin-bottom: 1rem;
        }}
        
        /* Responsive tables - horizontal scroll */
        .table-responsive {{
            display: block;
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        
        table {{
            min-width: 600px;
        }}
        
        /* Smaller font sizes on mobile */
        h1 {{
            font-size: 1.75rem !important;
        }}
        
        h2 {{
            font-size: 1.5rem !important;
        }}
        
        h3 {{
            font-size: 1.25rem !important;
        }}
        
        h4, h5, h6 {{
            font-size: 1.1rem !important;
        }}
        
        /* Adjust padding/margins */
        .welcome-banner {{
            padding: 15px !important;
            font-size: 0.95rem !important;
        }}
        
        .footer-custom {{
            padding: 15px 0 !important;
            font-size: 0.9rem !important;
        }}
        
        /* Responsive modal */
        .modal-dialog {{
            margin: 0.5rem !important;
        }}
        
        .modal-content {{
            border-radius: 0.5rem !important;
        }}
        
        /* Bet slip adjustments */
        .bet-slip {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            max-height: 50vh;
            overflow-y: auto;
            z-index: 1040;
        }}
        
        /* Sports list - better spacing */
        .sport-card, .match-card, .event-card {{
            padding: 12px !important;
            margin-bottom: 10px !important;
        }}
        
        /* Odds buttons - grid layout */
        .odds-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
            gap: 8px;
        }}
        
        .odds-button {{
            width: 100%;
            text-align: center;
        }}
    }}
    
    /* Tablet optimizations (768px - 1024px) */
    @media (min-width: 769px) and (max-width: 1024px) {{
        .container {{
            max-width: 100% !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
        }}
        
        .btn, button {{
            min-height: 40px !important;
            padding: 10px 14px !important;
        }}
    }}
    
    /* Mobile landscape */
    @media (max-width: 768px) and (orientation: landscape) {{
        .navbar {{
            padding: 0.25rem 1rem !important;
        }}
        
        .modal-dialog {{
            max-width: 90vw !important;
        }}
    }}
    
    /* Extra small screens */
    @media (max-width: 480px) {{
        body {{
            font-size: 14px !important;
        }}
        
        .btn, button {{
            font-size: 14px !important;
            padding: 10px 12px !important;
        }}
        
        .navbar-brand {{
            font-size: 1rem !important;
        }}
        
        h1 {{
            font-size: 1.5rem !important;
        }}
        
        h2 {{
            font-size: 1.3rem !important;
        }}
        
        /* Stack odds buttons vertically on very small screens */
        .odds-container {{
            grid-template-columns: 1fr 1fr;
        }}
    }}
    
    /* Prevent horizontal scroll */
    html, body {{
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }}
    
    /* Responsive images */
    img {{
        max-width: 100% !important;
        height: auto !important;
    }}
    
    /* Better mobile menu */
    .navbar-toggler {{
        border: none !important;
        padding: 0.5rem !important;
    }}
    
    @media (max-width: 768px) {{
        .navbar-collapse {{
            background-color: var(--secondary-color);
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 0.5rem;
        }}
    }}
    </style>
    """
    
    return css

def generate_custom_js(branding):
    """Generate custom JavaScript for operator-specific functionality"""
    operator = branding.get('operator', {})
    betting = branding.get('betting', {})
    features = branding.get('features', {})
    
    js = f"""
    <script>
    // Operator context and branding
    window.OPERATOR_CONTEXT = {{
        id: {operator.get('id', 0)},
        name: '{operator.get('name', 'Sportsbook')}',
        subdomain: '{operator.get('subdomain', '')}',
        email: '{operator.get('email', '')}',
        branding: {json.dumps(branding)}
    }};
    
    // Betting configuration
    window.BETTING_CONFIG = {{
        currency: '{betting.get('default_currency', 'USD')}',
        currencySymbol: '{betting.get('currency_symbol', '$')}',
        oddsFormat: '{betting.get('odds_format', 'decimal')}',
        minBet: {betting.get('min_bet', 1.0)},
        maxBet: {betting.get('max_bet', 10000.0)},
        maxPayout: {betting.get('max_payout', 100000.0)}
    }};
    
    // Feature flags
    window.FEATURES = {{
        liveBetting: {str(features.get('live_betting', True)).lower()},
        cashOut: {str(features.get('cash_out', True)).lower()},
        multiBet: {str(features.get('multi_bet', True)).lower()},
        liveStreaming: {str(features.get('live_streaming', False)).lower()},
        statistics: {str(features.get('statistics', True)).lower()},
        promotions: {str(features.get('promotions', True)).lower()}
    }};
    
    // Initialize operator-specific functionality
    document.addEventListener('DOMContentLoaded', function() {{
        // Update page title
        document.title = window.OPERATOR_CONTEXT.name + ' - Sports Betting Platform';
        
        // Update favicon if provided
        const faviconUrl = window.OPERATOR_CONTEXT.branding.branding?.favicon_url;
        if (faviconUrl) {{
            const favicon = document.querySelector('link[rel="icon"]') || document.createElement('link');
            favicon.rel = 'icon';
            favicon.href = faviconUrl;
            document.head.appendChild(favicon);
        }}
        
        // Add welcome banner if enabled
        const welcomeMessage = window.OPERATOR_CONTEXT.branding.branding?.welcome_message;
        if (welcomeMessage) {{
            const banner = document.createElement('div');
            banner.className = 'welcome-banner';
            banner.innerHTML = '<h4>' + welcomeMessage + '</h4>';
            
            const container = document.querySelector('.container') || document.body;
            container.insertBefore(banner, container.firstChild);
        }}
        
        // Update logo if provided
        const logoUrl = window.OPERATOR_CONTEXT.branding.branding?.logo_url;
        if (logoUrl) {{
            const logos = document.querySelectorAll('.navbar-brand, .logo');
            logos.forEach(logo => {{
                logo.innerHTML = '<img src="' + logoUrl + '" alt="' + window.OPERATOR_CONTEXT.name + '" class="brand-logo">';
            }});
        }}
        
        // Add custom footer
        const footerText = window.OPERATOR_CONTEXT.branding.branding?.footer_text;
        if (footerText) {{
            const footer = document.createElement('footer');
            footer.className = 'footer-custom text-center';
            footer.innerHTML = '<div class="container"><p>' + footerText + '</p></div>';
            document.body.appendChild(footer);
        }}
        
        // Initialize currency formatting
        window.formatCurrency = function(amount) {{
            return window.BETTING_CONFIG.currencySymbol + parseFloat(amount).toFixed(2);
        }};
        
        // Initialize odds formatting
        window.formatOdds = function(odds) {{
            const format = window.BETTING_CONFIG.oddsFormat;
            switch(format) {{
                case 'fractional':
                    return convertToFractional(odds);
                case 'american':
                    return convertToAmerican(odds);
                default:
                    return parseFloat(odds).toFixed(2);
            }}
        }};
        
        function convertToFractional(decimal) {{
            const fraction = decimal - 1;
            // Simple fraction conversion (could be enhanced)
            return fraction.toFixed(2) + '/1';
        }}
        
        function convertToAmerican(decimal) {{
            if (decimal >= 2) {{
                return '+' + Math.round((decimal - 1) * 100);
            }} else {{
                return '-' + Math.round(100 / (decimal - 1));
            }}
        }}
        
        console.log('🎨 Operator branding initialized for:', window.OPERATOR_CONTEXT.name);
    }});
    </script>
    """
    
    return js

@branding_bp.route('/api/branding/<subdomain>')
def get_branding_api(subdomain):
    """API endpoint to get operator branding"""
    branding = get_operator_branding(subdomain)
    
    if not branding:
        return jsonify({
            'success': False,
            'error': 'Operator not found or inactive'
        }), 404
    
    return jsonify({
        'success': True,
        'branding': branding
    })

@branding_bp.route('/api/branding/<subdomain>/update', methods=['POST'])
def update_branding(subdomain):
    """Update operator branding settings"""
    try:
        # This would require admin authentication
        # For now, just return the structure
        
        data = request.get_json()
        
        from src.db_compat import connection_ctx
        
        with connection_ctx(timeout=5) as conn:
            # keep the slot short & safe
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '2000ms'")
            # transaction ensures we never leave INTRANS on exceptions
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, settings FROM sportsbook_operators WHERE subdomain = %s",
                        (subdomain,),
                    )
                    operator = cur.fetchone()
                    if not operator:
                        return jsonify({'success': False, 'error': 'Operator not found'}), 404
                    op_settings_raw = operator.get('settings')
                    current_settings = json.loads(op_settings_raw) if op_settings_raw else {}
                    def _deep_merge(dst, src):
                        for k, v in (src or {}).items():
                            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                                _deep_merge(dst[k], v)
                            else:
                                dst[k] = v
                        return dst
                    _deep_merge(current_settings, data)
                    cur.execute(
                        "UPDATE sportsbook_operators SET settings=%s, updated_at=%s WHERE subdomain=%s",
                        (json.dumps(current_settings), datetime.now(), subdomain),
                    )
        
        # Invalidate cache after update (both Redis and in-process)
        from src.utils.redis_cache import invalidate_tenant_cache
        invalidate_tenant_cache(subdomain)
        
        # Also clear in-process cache
        cache_key = f"branding:{subdomain}"
        if cache_key in _BRANDING_CACHE:
            del _BRANDING_CACHE[cache_key]
        
        logger.info(f"🗑️ Invalidated branding cache for {subdomain} after update")
        
        return jsonify({
            'success': True,
            'message': 'Branding updated successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def warm_branding_cache(subdomains=None):
    """
    Pre-warm branding cache on boot to prevent stampeding on first requests.
    
    Args:
        subdomains: List of subdomain strings to pre-warm. If None, fetches all active operators.
    """
    logging.info("🔥 Pre-warming branding cache...")
    
    try:
        if subdomains is None:
            # Fetch all active operators from database
            with connection_ctx(timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '2000ms'")
                    cur.execute("SELECT subdomain FROM sportsbook_operators WHERE is_active = TRUE")
                    rows = cur.fetchall()
                    subdomains = [row['subdomain'] for row in rows]
        
        warmed_count = 0
        for subdomain in subdomains:
            try:
                get_operator_branding(subdomain)
                warmed_count += 1
                logging.info(f"✅ Warmed cache for: {subdomain}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to warm cache for {subdomain}: {e}")
        
        logging.info(f"🔥 Pre-warmed {warmed_count}/{len(subdomains)} branding caches")
        
    except Exception as e:
        logging.error(f"❌ Error warming branding cache: {e}")
        # Best effort - don't fail app startup if cache warming fails


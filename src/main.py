import os
import sys
import time
# Add src directory to Python path for proper imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables deterministically (env.local wins locally)
from src.config.env_loader import *  # noqa: F401 - just to execute the loader

# Production guard: ensure DATABASE_URL is set
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set; production must use Postgres, not sqlite.")

from flask import Flask, send_from_directory, send_file, request, redirect, session, current_app, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS
from flask_socketio import SocketIO
# Removed Flask-Session - using Flask's built-in signed-cookie sessions
from flask_sqlalchemy import SQLAlchemy
# Remove the import of db from betting models - we'll create our own
# from src.models.betting import db
from src.routes.auth import auth_bp
from src.routes.json_sports import json_sports_bp
from src.routes.sports import sports_bp
from src.routes.public_leaderboard import public_leaderboard_bp
# Move betting routes import to after database initialization to avoid circular dependency
# from src.routes.betting import betting_bp
from src.routes.prematch_odds import prematch_odds_bp
from src.websocket_service import LiveOddsWebSocketService, init_websocket_handlers
from src.live_odds_cache_service import get_live_odds_cache_service
from src.prematch_odds_service import get_prematch_odds_service
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

# Set specific logger levels
logging.getLogger('werkzeug').setLevel(logging.INFO)
logging.getLogger('flask_socketio').setLevel(logging.INFO)

# Create logger for this module
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Trust Fly's reverse proxy for scheme/host so Flask sees https
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Create our own database instance
db = SQLAlchemy()

# Custom JSON provider to handle PostgreSQL types (datetime, date, Decimal, UUID) for Flask ≥ 2.3 / 3.x
from flask.json.provider import DefaultJSONProvider
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()  # "2025-08-20T18:05:00+08:00"
        if isinstance(obj, Decimal):
            return float(obj)  # or str(obj) if you must keep precision
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

# Set the custom JSON provider for the Flask app
app.json = CustomJSONProvider(app)

# Enable CORS for all routes with proper credentials support
CORS(app, 
     origins=[
         "http://localhost:5000", 
         "http://127.0.0.1:5000",
         "https://sportsbook.kryzel.io",
         "https://goalserve-sportsbook-backend.fly.dev",
     ], 
     supports_credentials=True, 
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Ensure proper encoding handling
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

# Initialize SocketIO with proper CORS for production
# Use wildcard for sportsbook.kryzel.io to allow all subdomain paths
cors_origins = [
    "https://sportsbook.kryzel.io",
    "https://www.sportsbook.kryzel.io",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "https://goalserve-sportsbook-backend.fly.dev",
    "https://goalserve-sportsbook.fly.dev",
]

socketio = SocketIO(
    app,
    async_mode="eventlet",  # CRITICAL: eventlet required for WebSocket support
    cors_allowed_origins=cors_origins,
    message_queue=os.getenv("REDIS_URL"),  # For multi-instance deployments
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    cookie=None,  # Use Flask session cookies instead
    manage_session=False,  # Use Flask sessions, not SocketIO sessions
    engineio_options={
        "allow_upgrades": True,  # Allow WebSocket upgrades
        "transports": ["polling", "websocket"],  # Allow both transports
        "max_http_buffer_size": 1000000,  # Increase buffer size
    }
)

# Add lightweight health check endpoint (no DB access)
@app.route('/health')
@app.route('/healthz')
def health_check():
    """Lightweight health check - NO database access to avoid pool saturation"""
    return {'ok': True, 'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()}

# Serve favicon without touching DB
@app.route('/favicon.ico')
def favicon():
    """Serve favicon without DB hit - return 204 if not found"""
    from flask import send_from_directory
    static_dir = os.path.join(app.root_path, 'static')
    favicon_path = os.path.join(static_dir, 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(static_dir, 'favicon.ico', mimetype='image/x-icon')
    else:
        # Return 204 No Content to prevent 404 in console
        return '', 204

@app.route('/user-leaderboard')
def user_leaderboard_page():
    """Serve public user leaderboard HTML page"""
    try:
        with open('src/static/user_leader.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error serving user leaderboard page: {e}")
        return f"Error loading leaderboard page: {str(e)}", 500

@app.route('/partner-leaderboard')
def partner_leaderboard_page():
    """Serve public partner leaderboard HTML page"""
    try:
        with open('src/static/partner_leader.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error serving partner leaderboard page: {e}")
        return f"Error loading leaderboard page: {str(e)}", 500

# Add route debug endpoint
@app.route('/debug/routes')
def debug_routes():
    """Debug endpoint to see all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    
    # Filter for auth-related routes
    auth_routes = [r for r in routes if 'auth' in r['rule'] or 'me' in r['rule']]
    
    return {
        'total_routes': len(routes),
        'auth_routes': auth_routes,
        'all_routes': routes
    }

# Add WebSocket health check endpoint
@app.route('/ws-health')
def websocket_health_check():
    """Check WebSocket service health"""
    return {
        'status': 'healthy', 
        'websocket_enabled': True,
        'async_mode': 'eventlet',
        'transport': 'websocket',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

# Assert db_compat source at startup
try:
    import src.db_compat as _dbc
    print("✅ Using db_compat:", _dbc.__file__)
except Exception as e:
    print(f"❌ db_compat import error: {e}")

# Debug route to verify db_compat source at runtime
@app.route('/debug/db_compat')
def debug_db_compat():
    """Debug route to verify which db_compat is being used"""
    try:
        import src.db_compat as _dbc
        return {
            'status': 'success',
            'db_compat_file': _dbc.__file__,
            'db_compat_path': str(_dbc.__file__),
            'message': 'db_compat source verified'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': 'Failed to verify db_compat source'
        }, 500



# Configuration - SECRET_KEY will be set in the config.update() below

# Database configuration - use PostgreSQL from environment variables
database_url = os.getenv('DATABASE_URL') or os.getenv('PG_DSN')
if not database_url:
    raise ValueError("DATABASE_URL environment variable is required")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import the new database configuration
from src.db import ENGINE, SessionLocal

# Log the database pool configuration
app.logger.info("DB pool class: %s", ENGINE.pool.__class__.__name__)

# Session configuration - Fix cookie issues for local development
from datetime import timedelta
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "please_set_me_and_keep_constant"),
    PREFERRED_URL_SCHEME="https",  # url_for(..., _external=True) defaults to https
    
    # Cookies: support both local dev and production
    SESSION_COOKIE_NAME="session",
    SESSION_COOKIE_SECURE=os.getenv("IS_PRODUCTION", "false").lower() == "true",  # True in production
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None" if os.getenv("IS_PRODUCTION", "false").lower() == "true" else "Lax",  # None for cross-origin in prod
    SESSION_COOKIE_DOMAIN=None,          # let browser default to host; avoid '.localhost'
    SESSION_COOKIE_PATH="/",
    
    REMEMBER_COOKIE_SECURE=False,      # Allow HTTP for local development
    REMEMBER_COOKIE_SAMESITE="Lax",
    
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    
    # Additional session settings for better compatibility
    SESSION_REFRESH_EACH_REQUEST=True
)

# Using Flask's built-in signed-cookie sessions (no Flask-Session needed)

# Add tenant-aware unauthorized handler
@app.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized access with tenant-aware redirects"""
    # For API/XHR requests, do NOT redirect; return JSON 401
    if request.path.startswith('/api') or 'application/json' in (request.headers.get('Accept', '') or ''):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    # Page navigation: tenant-aware redirect
    path = request.path.strip('/')
    segments = path.split('/') if path else []
    if segments and segments[0] not in ['api', 'static', 'admin', 'superadmin', 'login', 'register']:
        tenant = segments[0]
        return redirect(f'/{tenant}/login'), 302
    return redirect('/login'), 302

@app.errorhandler(403)
def forbidden(error):
    """Handle forbidden access with tenant-aware redirects"""
    # For API/XHR requests, do NOT redirect; return JSON 403
    if request.path.startswith('/api') or 'application/json' in (request.headers.get('Accept', '') or ''):
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    # Page navigation: tenant-aware redirect
    path = request.path.strip('/')
    segments = path.split('/') if path else []
    if segments and segments[0] not in ['api', 'static', 'admin', 'superadmin', 'login', 'register']:
        tenant = segments[0]
        return redirect(f'/{tenant}/login'), 302
    return redirect('/login'), 302

# Debug route to check session status
@app.route("/__whoami")
def whoami():
    """Check current session and user status"""
    return {
        'ok': True,
        'session_id': session.get('_id'),
        'session_data': dict(session),
        'path': request.path,
        'referer': request.headers.get('Referer'),
        'user_agent': request.headers.get('User-Agent'),
        'cookies': dict(request.cookies)
    }

@app.route("/<tenant>/__whoami")
def tenant_whoami(tenant):
    """Check tenant-specific session status"""
    return {
        'ok': True,
        'tenant': tenant,
        'session_id': session.get('_id'),
        'session_data': dict(session),
        'path': request.path,
        'referer': request.headers.get('Referer'),
        'user_agent': request.headers.get('User-Agent'),
        'cookies': dict(request.cookies)
    }



# Ensure proper UTF-8 handling
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Import sportsbook registration routes
from src.routes.sportsbook_registration import sportsbook_bp
# from src.routes.multitenant_routing import multitenant_bp  # Disabled - causes redirect issues
from src.routes.clean_multitenant_routing import clean_multitenant_bp
from src.routes.superadmin import superadmin_bp
from src.routes.tenant_admin import tenant_admin_bp
from src.routes.branding import branding_bp
from src.routes.tenant_auth import tenant_auth_bp

# Import comprehensive admin blueprints
from src.routes.comprehensive_admin import comprehensive_admin_bp
from src.routes.comprehensive_superadmin import comprehensive_superadmin_bp
from src.routes.rich_admin_interface import rich_admin_bp
from src.routes.rich_superadmin_interface1 import rich_superadmin_bp

# Import theme customization blueprint
from src.routes.theme_customization import theme_bp
from src.routes.public_apis import public_apis_bp
from src.routes.casino_api import casino_bp
from src.routes.health import health_bp

# Register blueprints in correct order - tenant_auth first to avoid conflicts
app.register_blueprint(tenant_auth_bp)  # Tenant auth routes first (more specific)
logger.info("✅ Registered tenant_auth_bp blueprint")
app.register_blueprint(rich_admin_bp)  # Rich admin interface
app.register_blueprint(rich_superadmin_bp)
app.register_blueprint(theme_bp, url_prefix='/api')  # Theme customization routes
app.register_blueprint(public_apis_bp)  # Public APIs for non-authenticated users
app.register_blueprint(public_leaderboard_bp)  # Public leaderboard routes
app.register_blueprint(auth_bp, url_prefix='/api/auth')  # General auth routes (less specific)
logger.info("✅ Registered auth_bp blueprint with /api/auth prefix")
app.register_blueprint(json_sports_bp, url_prefix='/api/sports')
app.register_blueprint(sports_bp, url_prefix='/api/sports')  # Fix: should be /api/sports not /api
app.register_blueprint(prematch_odds_bp, url_prefix='/api/prematch-odds')
app.register_blueprint(sportsbook_bp, url_prefix='/api')
app.register_blueprint(casino_bp)  # Casino API routes
app.register_blueprint(health_bp)  # Lightweight health check (no DB dependency)
# app.register_blueprint(multitenant_bp)  # Disable old multitenant routing - REMOVED
app.register_blueprint(clean_multitenant_bp)  # New clean URL routing
app.register_blueprint(superadmin_bp)
# app.register_blueprint(tenant_admin_bp)  # Disable conflicting admin routes - REMOVED
app.register_blueprint(branding_bp)

# Register comprehensive admin blueprints (but lower priority) - ALL DISABLED
# app.register_blueprint(comprehensive_admin_bp)  # Disable basic admin - REMOVED
app.register_blueprint(comprehensive_admin_bp)  # Enable comprehensive admin for working betting events API
# app.register_blueprint(comprehensive_superadmin_bp)  # Disable basic super admin - REMOVED

# Initialize database
db.init_app(app)
app.db = db  # Manually attach db to app so it can be accessed as app.db

# Database teardown: always return sessions after each request
@app.teardown_appcontext
def _remove_session(exc=None):
    """Remove database session after each request"""
    SessionLocal.remove()

@app.route("/health/db")
def db_health():
    """Check database connection health"""
    db = None
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        return {
            'ok': True,
            'database': 'connected',
            'pool_class': ENGINE.pool.__class__.__name__,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, 200
    except Exception as e:
        return {
            'ok': False,
            'database': 'error',
            'error': str(e),
            'pool_class': ENGINE.pool.__class__.__name__,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, 500
    finally:
        if db:
            close_db(db)

# Bind the betting models to our database instance
from src.models.betting import bind_models_to_db
bind_models_to_db(db)

# Defer database initialization until app starts
def init_database():
    """Initialize database tables when the app starts"""
    try:
        with app.app_context():
            db.create_all()
            logging.info("✅ Database tables initialized successfully")
    except Exception as e:
        logging.error(f"❌ Failed to initialize database tables: {e}")
        # Don't crash the app, just log the error

# Now import betting routes after models are bound
from src.routes.betting import betting_bp

# Register betting blueprint after models are bound
app.register_blueprint(betting_bp, url_prefix='/api/betting')

# Register memory monitor blueprint (if available)
if os.getenv("DISABLE_MEMORY_MONITOR", "0") != "1":
    try:
        from src.routes.memory_monitor import memory_bp
        app.register_blueprint(memory_bp, url_prefix='/api')
        print("✅ Memory monitor blueprint registered")
    except ImportError as e:
        print(f"⚠️ Memory monitor disabled - psutil not available: {e}")
        logging.info(f"Memory monitor disabled due to missing psutil: {e}")
else:
    print("⏭️ Memory monitor disabled via DISABLE_MEMORY_MONITOR")
    logging.info("⏭️ Memory monitor disabled via DISABLE_MEMORY_MONITOR")

# Note: Alias route removed - using the proxy route below instead

# Initialize WebSocket service
live_odds_service = LiveOddsWebSocketService(socketio)
init_websocket_handlers(socketio, live_odds_service)

# Initialize Live Odds System
def init_live_odds_system():
    """Initialize the live odds system with both services"""
    try:
        logger = logging.getLogger(__name__)
        logger.info("🚀 Initializing Live Odds System...")
        
        # Get service instances
        prematch_service = get_prematch_odds_service()
        cache_service = get_live_odds_cache_service()
        
        # Start the cache service
        if not cache_service.start():
            logger.error("❌ Failed to start Live Odds Cache Service")
            return False
        
        logger.info("✅ Live Odds Cache Service started")
        
        # Integrate the services: when odds are updated, update the cache
        prematch_service.add_odds_updated_callback(cache_service.on_odds_updated)
        
        logger.info("✅ Live Odds System integrated successfully")
        logger.info("🎯 Live odds updates will now automatically update cache and trigger UI updates")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing Live Odds System: {e}")
        return False

# Initialize live odds system
init_live_odds_system()

# API endpoint to check if odds have been updated for a sport
@app.route('/api/sports/odds-status/<sport>')
def get_odds_status(sport):
    """Get the last update timestamp for a sport's odds"""
    try:
        cache_service = get_live_odds_cache_service()
        if cache_service and sport in cache_service.cache_timestamps:
            timestamp = cache_service.cache_timestamps[sport]
            return {
                'sport': sport,
                'last_updated': timestamp.isoformat() if timestamp else None,
                'has_data': sport in cache_service.cache_data and len(cache_service.cache_data[sport]) > 0
            }
        else:
            return {
                'sport': sport,
                'last_updated': None,
                'has_data': False
            }
    except Exception as e:
        logging.error(f"Error getting odds status for {sport}: {e}")
        return {'error': str(e)}, 500

# WebSocket connection management for user-specific rooms
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection and join user to personal room"""
    try:
        from flask import session
        # Check both possible session formats: user_id directly or user_data.id
        user_id = session.get('user_id') or (session.get('user_data', {}).get('id') if session.get('user_data') else None)
        if user_id:
            # Join user to their personal room for balance updates
            from flask_socketio import join_room
            join_room(f'user_{user_id}')
            print(f"✅ User {user_id} joined WebSocket room: user_{user_id}")
        else:
            print("⚠️ WebSocket connected but no user_id in session")
            print(f"⚠️ Session keys: {list(session.keys())}")
    except Exception as e:
        print(f"❌ Error in WebSocket connect handler: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    try:
        from flask import session
        user_id = session.get('user_id')
        if user_id:
            print(f"🔌 User {user_id} disconnected from WebSocket")
    except Exception as e:
        print(f"❌ Error in WebSocket disconnect handler: {e}")

# Initialize bet settlement service
from src.bet_settlement_service import BetSettlementService
bet_settlement_service = BetSettlementService(app)

# Initialize pre-match odds service
from src.prematch_odds_service import get_prematch_odds_service
prematch_odds_service = get_prematch_odds_service()

# Start the bet settlement service automatically when the module is imported
try:
    bet_settlement_service.start()
    logging.info("✅ Bet settlement service started automatically")
except Exception as e:
    logging.error(f"❌ Failed to start bet settlement service automatically: {e}")

# Start the pre-match odds service automatically when the module is imported
try:
    prematch_odds_service.start()
    logging.info("✅ Pre-match odds service started automatically")
except Exception as e:
    logging.error(f"❌ Failed to start pre-match odds service automatically: {e}")

def ensure_settlement_service_running():
    """Ensure the settlement service is running, restart if needed"""
    if not bet_settlement_service.running:
        logging.warning("🔄 Settlement service not running, attempting restart...")
        try:
            success = bet_settlement_service.start()
            if success:
                logging.info("✅ Settlement service restarted successfully")
            else:
                logging.error("❌ Failed to restart settlement service")
        except Exception as e:
            logging.error(f"❌ Error restarting settlement service: {e}")

def ensure_prematch_odds_service_running():
    """Ensure the pre-match odds service is running, restart if needed"""
    if not prematch_odds_service.running:
        logging.warning("🔄 Pre-match odds service not running, attempting restart...")
        try:
            success = prematch_odds_service.start()
            if success:
                logging.info("✅ Pre-match odds service restarted successfully")
            else:
                logging.error("❌ Failed to restart pre-match odds service")
        except Exception as e:
            logging.error(f"❌ Error restarting pre-match odds service: {e}")

def ensure_live_odds_cache_service_running():
    """Ensure the live odds cache service is running, restart if needed"""
    try:
        cache_service = get_live_odds_cache_service()
        if not cache_service.running:
            logging.warning("🔄 Live odds cache service not running, attempting restart...")
            try:
                success = cache_service.start()
                if success:
                    logging.info("✅ Live odds cache service restarted successfully")
                else:
                    logging.error("❌ Failed to restart live odds cache service")
            except Exception as e:
                logging.error(f"❌ Error restarting live odds cache service: {e}")
    except Exception as e:
        logging.error(f"❌ Error checking live odds cache service: {e}")



# Schedule periodic health checks for services
import atexit
import signal
import threading

def periodic_health_check():
    """Periodic health check for all services"""
    while True:
        try:
            # Check settlement service
            ensure_settlement_service_running()
            
                        # Check pre-match odds service
            ensure_prematch_odds_service_running()
            
            # Check live odds cache service
            ensure_live_odds_cache_service_running()
            
            # Wait 5 minutes before next check
            time.sleep(300)
        except Exception as e:
            logging.error(f"❌ Error in periodic health check: {e}")
            time.sleep(60)  # Wait 1 minute on error

# Start periodic health check in background thread
health_check_thread = threading.Thread(target=periodic_health_check, daemon=True)
health_check_thread.start()
logging.info("✅ Periodic health check service started")

def cleanup_services():
    """Cleanup services on shutdown"""
    logging.info("🛑 Shutting down services...")
    try:
        bet_settlement_service.stop()
        live_odds_service.stop()
        prematch_odds_service.stop()
        # Don't close the pool immediately - let it be cleaned up by the process
        logging.info("✅ Services stopped gracefully")
    except Exception as e:
        logging.error(f"❌ Error during cleanup: {e}")

atexit.register(cleanup_services)

# Handle graceful shutdown
def signal_handler(signum, frame):
    logging.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    cleanup_services()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@app.route('/api/health', methods=['GET'])
def api_health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from src.database_config import test_database_connection, get_connection_pool_status
        db_healthy, db_message = test_database_connection()
        pool_status = get_connection_pool_status()
        
        return {
            'status': 'healthy' if db_healthy else 'degraded',
            'service': 'GoalServe Sports Betting Platform',
            'version': '1.0.0',
            'database': {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'message': db_message,
                'pool_status': pool_status
            },
            'websocket_clients': live_odds_service.get_connected_clients_count(),
            'prematch_odds_service': {
                'status': 'healthy' if prematch_odds_service.running else 'unhealthy',
                'running': prematch_odds_service.running,
                'stats': prematch_odds_service.get_stats()
            }
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'GoalServe Sports Betting Platform',
            'version': '1.0.0',
            'error': str(e)
        }, 500

@app.route('/api/websocket/status', methods=['GET'])
def websocket_status():
    """WebSocket service status endpoint"""
    return {
        'service_running': live_odds_service.running,
        'connected_clients': live_odds_service.get_connected_clients_count(),
        'update_interval': live_odds_service.update_interval,
        'critical_matches': live_odds_service.get_critical_matches(),
        'current_update_frequency': '1 second' if live_odds_service.critical_matches else f'{live_odds_service.update_interval} seconds'
    }

@app.route('/api/prematch-odds/status', methods=['GET'])
def prematch_odds_status():
    """Pre-match odds service status endpoint"""
    return {
        'service_running': prematch_odds_service.running,
        'stats': prematch_odds_service.get_stats(),
        'recent_files': prematch_odds_service.get_recent_files(limit=5)
    }

@app.route('/api/db/pool-status', methods=['GET'])
def db_pool_status():
    """Database connection pool status endpoint"""
    try:
        from src.db_compat import pool as get_pool
        
        # Get pool status
        pool = get_pool()
        
        # Get SQLAlchemy pool info
        sqlalchemy_pool_info = {}
        try:
            engine = db.get_engine()
            sqlalchemy_pool_info = {
                'size': engine.pool.size(),
                'checked_in': engine.pool.checkedin(),
                'checked_out': engine.pool.checkedout(),
                'overflow': engine.pool.overflow()
            }
            # Only add 'invalid' if the pool supports it
            if hasattr(engine.pool, 'invalid'):
                sqlalchemy_pool_info['invalid'] = engine.pool.invalid()
        except Exception as e:
            sqlalchemy_pool_info = {'error': str(e)}
        
        # Get raw pool stats
        raw_pool_stats = pool.get_pool_stats() if hasattr(pool, 'get_pool_stats') else {}
        
        # Calculate pool health - ensure all values are integers
        raw_size = raw_pool_stats.get('size', 0)
        raw_checked_out = raw_pool_stats.get('checked_out', 0)
        sqlalchemy_size = sqlalchemy_pool_info.get('size', 0)
        sqlalchemy_checked_out = sqlalchemy_pool_info.get('checked_out', 0)
        
        # Convert to integers, defaulting to 0 if not numeric
        try:
            raw_size = int(raw_size) if isinstance(raw_size, (int, float)) else 0
            raw_checked_out = int(raw_checked_out) if isinstance(raw_checked_out, (int, float)) else 0
            sqlalchemy_size = int(sqlalchemy_size) if isinstance(sqlalchemy_size, (int, float)) else 0
            sqlalchemy_checked_out = int(sqlalchemy_checked_out) if isinstance(sqlalchemy_checked_out, (int, float)) else 0
        except (ValueError, TypeError):
            raw_size = raw_checked_out = sqlalchemy_size = sqlalchemy_checked_out = 0
        
        total_connections = raw_size + sqlalchemy_size
        used_connections = raw_checked_out + sqlalchemy_checked_out
        connection_usage = (used_connections / total_connections * 100) if total_connections > 0 else 0
        
        health_status = 'healthy'
        if connection_usage > 80:
            health_status = 'warning'
        elif connection_usage > 95:
            health_status = 'critical'
        
        return {
            'status': health_status,
            'connection_usage_percent': round(connection_usage, 2),
            'total_connections': total_connections,
            'used_connections': used_connections,
            'raw_pool': raw_pool_stats,
            'sqlalchemy_pool': sqlalchemy_pool_info,
            'message': f'Database pools at {connection_usage:.1f}% capacity'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': 'Failed to get pool status'
        }, 500

@app.route('/api/db/pool-reset', methods=['POST'])
def db_pool_reset():
    """Reset database connection pools (emergency recovery)"""
    try:
        from src.db_compat import pool as get_pool
        
        # Force recreation of pools (emergency only - not recommended)
        # Note: Pool recreation is now handled automatically
        import gc
        gc.collect()
        
        # Test pool is accessible
        test_pool = get_pool()
        
        return {
            'status': 'success',
            'message': 'Database pools reset successfully'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': 'Failed to reset pools'
        }, 500

@app.route('/api/websocket/start', methods=['POST'])
def start_websocket_service():
    """Start the WebSocket live odds service"""
    try:
        live_odds_service.start()
        return {'status': 'started', 'message': 'Live odds WebSocket service started'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/websocket/stop', methods=['POST'])
def stop_websocket_service():
    """Stop the WebSocket live odds service"""
    try:
        live_odds_service.stop()
        return {'status': 'stopped', 'message': 'Live odds WebSocket service stopped'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/settlement/status', methods=['GET'])
def settlement_status():
    """Get bet settlement service status"""
    return {
        'service_running': bet_settlement_service.running,
        'check_interval': bet_settlement_service.check_interval,
        'stats': bet_settlement_service.get_settlement_stats()
    }

@app.route('/api/settlement/start', methods=['POST'])
def start_settlement_service():
    """Start the automatic bet settlement service"""
    try:
        bet_settlement_service.start()
        return {'status': 'started', 'message': 'Automatic bet settlement service started'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/settlement/stop', methods=['POST'])
def stop_settlement_service():
    """Stop the automatic bet settlement service"""
    try:
        bet_settlement_service.stop()
        return {'status': 'stopped', 'message': 'Automatic bet settlement service stopped'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/settlement/force/<match_name>', methods=['POST'])
def force_settle_match(match_name):
    """Force settlement for a specific match"""
    try:
        bet_settlement_service.force_settle_match(match_name)
        return {'status': 'success', 'message': f'Force settlement triggered for {match_name}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/monitoring/dashboard', methods=['GET'])
def monitoring_dashboard():
    """Comprehensive monitoring dashboard"""
    try:
        # Get settlement service stats
        settlement_stats = bet_settlement_service.get_settlement_stats()
        
        # Get WebSocket service stats
        websocket_stats = {
            'service_running': live_odds_service.running,
            'connected_clients': live_odds_service.get_connected_clients_count(),
            'update_interval': live_odds_service.update_interval,
            'critical_matches': live_odds_service.get_critical_matches()
        }
        
        # Get database stats
        from src.models.betting import Bet, User, Transaction
        with app.app_context():
            db_stats = {
                'total_users': current_app.db.session.query(User).count(),
                'total_bets': current_app.db.session.query(Bet).count(),
                'pending_bets': current_app.db.session.query(Bet).filter_by(status='pending').count(),
                'won_bets': current_app.db.session.query(Bet).filter_by(status='won').count(),
                'lost_bets': current_app.db.session.query(Bet).filter_by(status='lost').count(),
                'void_bets': current_app.db.session.query(Bet).filter_by(status='void').count(),
                'total_transactions': current_app.db.session.query(Transaction).count()
            }
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'services': {
                'settlement_service': settlement_stats,
                'websocket_service': websocket_stats
            },
            'database': db_stats,
            'system': {
                'python_version': sys.version,
                'platform': sys.platform
            }
        }
        
    except Exception as e:
        return {'error': str(e)}, 500

@app.errorhandler(404)
def not_found(error):
    return {'error': 'Not found'}, 404

@app.errorhandler(500)
def internal_error(error):
    return {'error': 'Internal server error'}, 500

@app.errorhandler(UnicodeDecodeError)
def unicode_decode_error(error):
    return {'error': f'Unicode decoding error: {str(error)}'}, 500

# Proxy route for Google OAuth login to match Google console redirect URI
@app.route('/auth/google/login', methods=['GET'])
def google_oauth_login_proxy():
    # Forward all query params to the actual API login under the blueprint
    query_string = request.query_string.decode() if request.query_string else ''
    target = '/api/auth/google/login'
    if query_string:
        target = f"{target}?{query_string}"
    return redirect(target, code=302)

# Proxy route for Google OAuth callback to match Google console redirect URI
@app.route('/auth/google/callback', methods=['GET'])
def google_oauth_callback_proxy():
    # Forward all query params to the actual API callback under the blueprint
    query_string = request.query_string.decode() if request.query_string else ''
    target = '/api/auth/google/callback'
    if query_string:
        target = f"{target}?{query_string}"
    return redirect(target, code=302)

# Explicit route for the standalone login page to avoid redirect loops
@app.route('/login')
def serve_login():
    # Check if this is a subdomain request - if so, redirect to appropriate subdomain login
    referer = request.headers.get('Referer', '')
    if referer:
        # Extract subdomain from referer
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            path_parts = parsed.path.strip('/').split('/')
            if path_parts and path_parts[0] and not path_parts[0].startswith(('api', 'admin', 'static')):
                subdomain = path_parts[0]
                # Redirect to subdomain-specific login
                return redirect(f'/{subdomain}/login', code=302)
        except Exception:
            pass  # Fall back to default behavior
    
    static_folder_path = app.static_folder
    if static_folder_path is None:
        logging.error("Static folder not configured")
        return "Static folder not configured", 404
    
    if not os.path.exists(static_folder_path):
        logging.error(f"Static folder does not exist: {static_folder_path}")
        return "Static folder not found", 404
    
    try:
        return send_from_directory(static_folder_path, 'login.html')
    except Exception as e:
        logging.error(f"Error serving login.html: {e}")
        return f"Error serving login page: {str(e)}", 500

@app.route('/bulk-registration')
def serve_bulk_registration():
    """Serve the bulk registration page"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        logging.error("Static folder not configured")
        return "Static folder not configured", 404
    
    if not os.path.exists(static_folder_path):
        logging.error(f"Static folder does not exist: {static_folder_path}")
        return "Static folder not found", 404
    
    try:
        return send_from_directory(static_folder_path, 'bulk_registration.html')
    except Exception as e:
        logging.error(f"Error serving bulk_registration.html: {e}")
        return f"Error serving bulk registration page: {str(e)}", 500


# Catch-all route for static files - must be after all API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Don't serve static files for API routes
    if path.startswith('api/'):
        return "API endpoint not found", 404
    
    # Don't intercept any admin routes - let blueprints handle them completely
    if path.startswith('admin/'):
        return "Admin route should be handled by blueprint", 404
    
        # Handle sportsbook routes - these are handled by the multitenant blueprint
    if path.startswith('sportsbook/'):
        # These routes are handled by the multitenant blueprint
        # This should not be reached, but just in case
        return "Sportsbook route should be handled by blueprint", 404
        
    static_folder_path = app.static_folder
    if static_folder_path is None:
        logging.error("Static folder not configured")
        return "Static folder not configured", 404
    
    if not os.path.exists(static_folder_path):
        logging.error(f"Static folder does not exist: {static_folder_path}")
        return "Static folder not found", 404

    # Special-case for login without extension
    if path == 'login' or path == 'login.html':
        # Check if this is a subdomain request - if so, redirect to appropriate subdomain login
        referer = request.headers.get('Referer', '')
        if referer:
            # Extract subdomain from referer
            try:
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                path_parts = parsed.path.strip('/').split('/')
                if path_parts and path_parts[0] and not path_parts[0].startswith(('api', 'admin', 'static')):
                    subdomain = path_parts[0]
                    # Redirect to subdomain-specific login
                    return redirect(f'/{subdomain}/login', code=302)
            except Exception:
                pass  # Fall back to default behavior
        
        try:
            return send_from_directory(static_folder_path, 'login.html')
        except Exception as e:
            logging.error(f"Error serving login.html: {e}")
            return f"Error serving login page: {str(e)}", 500
    
    # Special case for sportsbook registration
    if path == 'register-sportsbook' or path == 'register-sportsbook.html':
        try:
            return send_from_directory(static_folder_path, 'register-sportsbook.html')
        except Exception as e:
            logging.error(f"Error serving register-sportsbook.html: {e}")
            return f"Error serving registration page: {str(e)}", 500

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        try:
            return send_from_directory(static_folder_path, path)
        except Exception as e:
            logging.error(f"Error serving static file {path}: {e}")
            return f"Error serving file: {str(e)}", 500
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            try:
                return send_from_directory(static_folder_path, 'index.html')
            except Exception as e:
                logging.error(f"Error serving index.html: {e}")
                return f"Error serving index.html: {str(e)}", 500
        else:
            logging.error(f"index.html not found at {index_path}")
            return "index.html not found", 404

if __name__ == '__main__':
    print("🚀 Starting GoalServe Sports Betting Platform...")
    print("🔧 Environment: Python", sys.version)
    
    # Pre-warm branding cache in background to prevent stampeding
    try:
        import threading
        from src.routes.branding import warm_branding_cache
        threading.Thread(target=warm_branding_cache, daemon=True).start()
    except Exception as e:
        logger.warning(f"⚠️ Failed to start cache warming: {e}")
    
    # Start pool metrics logging (Phase 2)
    try:
        def log_pool_metrics_periodically():
            while True:
                try:
                    from src.db_compat import log_pool_metrics
                    log_pool_metrics()
                except Exception as e:
                    logger.error(f"Pool metrics error: {e}")
                time.sleep(60)  # Log every minute
        
        threading.Thread(target=log_pool_metrics_periodically, daemon=True, name="pool-metrics").start()
        logger.info("✅ Pool metrics logging started (every 60s)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to start pool metrics: {e}")
    
    try:
        print("🔧 Flask version:", Flask.__version__)
    except AttributeError:
        print("🔧 Flask version: Unknown (__version__ attribute not available)")
    print("🔧 Working directory:", os.getcwd())
    print("🔧 Static folder:", app.static_folder)
    
    # Start the WebSocket service
    try:
        live_odds_service.start()
        print("✅ WebSocket service started successfully")
    except Exception as e:
        print(f"❌ Failed to start WebSocket service: {e}")
        logging.error(f"Failed to start WebSocket service: {e}")

    # Initialize database tables
    try:
        init_database()
        print("✅ Database initialization completed")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logging.error(f"Database initialization failed: {e}")

    # Start connection pool monitoring
    def monitor_connection_pools():
        """Monitor connection pool health and log warnings"""
        import threading
        
        def monitor_loop():
            while True:
                try:
                    from src.db_compat import pool as get_pool
                    db_pool = get_pool()
                    
                    if hasattr(pool, 'get_pool_stats'):
                        stats = pool.get_pool_stats()
                        usage = stats.get('checked_out', 0) / max(stats.get('max_size', 100), 1) * 100
                        
                        if usage > 80:
                            logging.warning(f"High connection pool usage: {usage:.1f}%")
                        elif usage > 95:
                            logging.error(f"Critical connection pool usage: {usage:.1f}%")
                            
                except Exception as e:
                    logging.error(f"Connection pool monitoring error: {e}")
                
                time.sleep(30)  # Check every 30 seconds
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        print("✅ Connection pool monitoring started")

    monitor_connection_pools()

# Start the automatic bet settlement service with delay to prevent startup overload
import threading
import time

def delayed_start_bet_settlement():
    """Start bet settlement service after a delay to prevent startup overload"""
    time.sleep(30)  # Wait 30 seconds after app starts
    try:
        bet_settlement_service.start()
        print("✅ Bet settlement service started successfully (delayed)")
        
        # Verify the service is running
        if bet_settlement_service.running:
            print(f"✅ Settlement service is running (check interval: {bet_settlement_service.check_interval}s)")
        else:
            print("❌ Settlement service failed to start")
            
    except Exception as e:
        print(f"❌ Failed to start bet settlement service: {e}")
        logging.error(f"Failed to start bet settlement service: {e}")

# Start bet settlement service in background thread with delay
settlement_thread = threading.Thread(target=delayed_start_bet_settlement, daemon=True)
settlement_thread.start()
print("⏳ Bet settlement service will start in 30 seconds...")

print("🌐 Flask application initialized successfully")
print("🔧 Ready for SocketIO to start the server")


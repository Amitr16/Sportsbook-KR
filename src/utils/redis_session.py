"""
Redis-based session storage to reduce database load
"""

import json
import pickle
import time
import logging
import redis
import os
from typing import Any, Optional, Dict
from flask import session, current_app
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict
import uuid

logger = logging.getLogger(__name__)

class RedisSession(CallbackDict, SessionMixin):
    """Redis-backed session storage"""
    
    def __init__(self, initial=None, sid=None, permanent=None):
        def on_update(self):
            self.modified = True
        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.permanent = permanent
        self.modified = False

class RedisSessionInterface(SessionInterface):
    """Flask session interface using Redis storage"""
    
    def __init__(self, redis_url: Optional[str] = None, 
                 prefix: str = 'session:',
                 use_signer: bool = True,
                 permanent_session_lifetime: int = 86400):
        self.redis_client = None
        self.prefix = prefix
        self.use_signer = use_signer
        self.permanent_session_lifetime = permanent_session_lifetime
        
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()  # Test connection
                logger.info("✅ Redis session storage initialized")
            except Exception as e:
                logger.warning(f"Redis session storage unavailable: {e}")
    
    def _get_redis_key(self, sid: str) -> str:
        """Generate Redis key for session"""
        return f"{self.prefix}{sid}"
    
    def generate_sid(self) -> str:
        """Generate secure session ID"""
        return str(uuid.uuid4())
    
    def open_session(self, app, request):
        """Open session from Redis"""
        # Get session cookie name safely
        cookie_name = app.config.get('SESSION_COOKIE_NAME', 'session')
        sid = request.cookies.get(cookie_name)
        
        # Default permanent to True for persistent sessions
        permanent = app.config.get('SESSION_PERMANENT', True)
        
        if not sid:
            sid = self.generate_sid()
            return RedisSession(sid=sid, permanent=permanent)
        
        if self.use_signer:
            signer = self.get_signing_serializer(app)
            if signer is None:
                sid = self.generate_sid()
                return RedisSession(sid=sid, permanent=permanent)
            try:
                sid_as_bytes = sid.encode('utf-8') if isinstance(sid, str) else sid
                sid = signer.loads(sid_as_bytes)
            except Exception:
                sid = self.generate_sid()
                return RedisSession(sid=sid, permanent=permanent)
        
        if not self.redis_client:
            return RedisSession(sid=sid, permanent=permanent)
        
        try:
            # Get session data from Redis
            redis_key = self._get_redis_key(sid)
            data = self.redis_client.get(redis_key)
            
            if data:
                # Deserialize session data
                session_data = pickle.loads(data)
                return RedisSession(session_data, sid=sid, permanent=permanent)
            else:
                # Session expired or doesn't exist
                return RedisSession(sid=sid, permanent=permanent)
                
        except Exception as e:
            logger.error(f"Error loading session {sid}: {e}")
            return RedisSession(sid=sid, permanent=permanent)
    
    def save_session(self, app, session, response):
        """Save session to Redis"""
        # Handle None session gracefully
        if session is None:
            return
        
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        
        if not session:
            if session.modified:
                # Delete session from Redis
                if self.redis_client and session.sid:
                    try:
                        redis_key = self._get_redis_key(session.sid)
                        self.redis_client.delete(redis_key)
                    except Exception as e:
                        logger.error(f"Error deleting session {session.sid}: {e}")
                
                cookie_name = app.config.get('SESSION_COOKIE_NAME', 'session')
                response.delete_cookie(cookie_name, domain=domain, path=path)
            return
        
        # Set cookie expiry
        if session.permanent:
            expires = self.get_expiration_time(app, session)
        else:
            expires = None
        
        # Save session to Redis
        if self.redis_client and session.modified:
            try:
                redis_key = self._get_redis_key(session.sid)
                session_data = pickle.dumps(dict(session))
                
                # Set expiry based on session type
                if session.permanent:
                    expiry = self.permanent_session_lifetime
                else:
                    expiry = 3600  # 1 hour for non-permanent sessions
                
                self.redis_client.setex(redis_key, expiry, session_data)
                
            except Exception as e:
                logger.error(f"Error saving session {session.sid}: {e}")
        
        # Set cookie
        if self.use_signer:
            signer = self.get_signing_serializer(app)
            if signer is not None:
                session_cookie = signer.dumps(session.sid)
            else:
                session_cookie = session.sid
        else:
            session_cookie = session.sid
        
        cookie_name = app.config.get('SESSION_COOKIE_NAME', 'session')
        response.set_cookie(cookie_name, session_cookie,
                          expires=expires, httponly=True,
                          domain=domain, path=path, secure=False, samesite='Lax')

# Global session interface
_session_interface = None

def init_redis_sessions(app, redis_url: Optional[str] = None):
    """Initialize Redis session storage for Flask app"""
    global _session_interface
    
    if _session_interface is None:
        _session_interface = RedisSessionInterface(redis_url)
    
    app.session_interface = _session_interface
    logger.info("✅ Redis session storage configured")

def get_session_stats() -> Dict[str, Any]:
    """Get Redis session statistics"""
    if not _session_interface or not _session_interface.redis_client:
        return {'error': 'Redis sessions not available'}
    
    try:
        # Get all session keys
        session_keys = _session_interface.redis_client.keys(f"{_session_interface.prefix}*")
        
        return {
            'total_sessions': len(session_keys),
            'redis_available': True,
            'prefix': _session_interface.prefix
        }
    except Exception as e:
        return {'error': f'Failed to get session stats: {e}'}

def cleanup_expired_sessions():
    """Clean up expired sessions (Redis handles this automatically with TTL)"""
    # Redis handles TTL automatically, but we can add manual cleanup if needed
    pass

# Session helper functions
def get_session_data(key: str, default: Any = None) -> Any:
    """Get data from current session"""
    return session.get(key, default)

def set_session_data(key: str, value: Any):
    """Set data in current session"""
    session[key] = value
    session.permanent = True  # Make session persistent

def clear_session_data(key: str):
    """Clear specific data from session"""
    session.pop(key, None)

def clear_all_session_data():
    """Clear all session data"""
    session.clear()

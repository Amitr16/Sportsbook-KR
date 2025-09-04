"""
Multi-user session management for the sports betting platform
Handles concurrent user sessions without conflicts
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import threading

logger = logging.getLogger(__name__)

class MultiUserSessionManager:
    """Manages multiple concurrent user sessions"""
    
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600  # 1 hour
        self._session_timeout = 86400   # 24 hours
        
    def create_session(self, user_id: int, operator_id: int, username: str, subdomain: str) -> str:
        """Create a new user session"""
        session_id = f"user_{user_id}_{operator_id}_{int(time.time())}"
        
        with self._lock:
            self._sessions[session_id] = {
                'user_id': user_id,
                'operator_id': operator_id,
                'username': username,
                'subdomain': subdomain,
                'created_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'data': {}
            }
            
        logger.info(f"Created session {session_id} for user {username} in {subdomain}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID"""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                # Update last activity
                session['last_activity'] = datetime.utcnow()
                return session
        return None
    
    def update_session_data(self, session_id: str, key: str, value: Any) -> bool:
        """Update session data"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]['data'][key] = value
                self._sessions[session_id]['last_activity'] = datetime.utcnow()
                return True
        return False
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session"""
        with self._lock:
            if session_id in self._sessions:
                user_info = self._sessions[session_id]
                del self._sessions[session_id]
                logger.info(f"Removed session {session_id} for user {user_info['username']}")
                return True
        return False
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = datetime.utcnow()
        expired_sessions = []
        
        with self._lock:
            for session_id, session_data in self._sessions.items():
                if (now - session_data['last_activity']).total_seconds() > self._session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        with self._lock:
            return len(self._sessions)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session info without updating last_activity"""
        with self._lock:
            return self._sessions.get(session_id)

# Global session manager instance
session_manager = MultiUserSessionManager()

def get_session_manager() -> MultiUserSessionManager:
    """Get the global session manager instance"""
    return session_manager

"""
SQLAlchemy Session Tracker - Wraps SQLAlchemy sessions to track connections
"""

import threading
import time
from contextlib import contextmanager
from flask import has_request_context, request
import inspect

# Track SQLAlchemy session usage
_sqlalchemy_sessions = {}
_session_lock = threading.Lock()

def get_current_context():
    """Get current route/function context"""
    if has_request_context():
        return f"{request.method} {request.path}"
    else:
        # For background workers
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back.f_back
            function_name = caller_frame.f_code.co_name
            filename = caller_frame.f_code.co_filename.split('\\')[-1]
            return f"{filename}::{function_name}"
        except:
            return "background_worker"
        finally:
            del frame

@contextmanager
def track_sqlalchemy_session(session, context_name="sqlalchemy_session"):
    """Track a SQLAlchemy session with connection tracking"""
    session_id = id(session)
    start_time = time.time()
    
    with _session_lock:
        _sqlalchemy_sessions[session_id] = {
            'context': context_name,
            'start_time': start_time,
            'active': True
        }
    
    try:
        # Import connection tracker
        from src.utils.connection_tracker import track_connection_acquired
        track_context, track_start = track_connection_acquired(context_name)
        
        yield session
        
    finally:
        # Track session completion
        duration = time.time() - start_time
        with _session_lock:
            if session_id in _sqlalchemy_sessions:
                _sqlalchemy_sessions[session_id]['active'] = False
                _sqlalchemy_sessions[session_id]['duration'] = duration
                
        # Track connection release
        try:
            from src.utils.connection_tracker import track_connection_released
            track_connection_released(track_context, track_start)
        except Exception:
            pass

def get_sqlalchemy_session_stats():
    """Get statistics about SQLAlchemy session usage"""
    with _session_lock:
        active_sessions = sum(1 for s in _sqlalchemy_sessions.values() if s.get('active', False))
        total_sessions = len(_sqlalchemy_sessions)
        
        return {
            'active_sessions': active_sessions,
            'total_sessions': total_sessions,
            'sessions': dict(_sqlalchemy_sessions)
        }

def reset_sqlalchemy_tracking():
    """Reset SQLAlchemy session tracking"""
    with _session_lock:
        _sqlalchemy_sessions.clear()

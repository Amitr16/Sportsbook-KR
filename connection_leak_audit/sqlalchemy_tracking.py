
# SQLAlchemy Session Tracking Wrapper
import threading
import time
from sqlalchemy.orm import Session

class TrackedSession(Session):
    """SQLAlchemy Session with connection tracking"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tracking_context = f"sqlalchemy_session_{id(self)}"
        self._tracking_start = time.time()
        
        # Track session creation
        try:
            from src.utils.connection_tracker import track_connection_acquired
            context, track_start = track_connection_acquired(self._tracking_context)
            self._tracking_context = context
            self._tracking_start = track_start
        except Exception:
            pass
    
    def close(self):
        """Close session with tracking"""
        try:
            from src.utils.connection_tracker import track_connection_released
            track_connection_released(self._tracking_context, self._tracking_start)
        except Exception:
            pass
        super().close()

# Patch the SessionLocal to use TrackedSession
def patch_session_local():
    """Patch SessionLocal to use tracked sessions"""
    try:
        from src.db import SessionLocal
        original_call = SessionLocal.__call__
        
        def tracked_call():
            session = original_call()
            # Wrap the session with tracking
            session.__class__ = type('TrackedSession', (TrackedSession, session.__class__), {})
            session._tracking_context = f"sqlalchemy_session_{id(session)}"
            session._tracking_start = time.time()
            return session
        
        SessionLocal.__call__ = tracked_call
        print("Patched SessionLocal with connection tracking")
    except Exception as e:
        print(f"Failed to patch SessionLocal: {e}")

# Auto-patch on import
patch_session_local()

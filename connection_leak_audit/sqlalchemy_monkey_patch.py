"""
SQLAlchemy Monkey Patch - Automatically track all SQLAlchemy sessions
"""

def patch_sqlalchemy_sessions():
    """Monkey patch SQLAlchemy to automatically track sessions"""
    try:
        from sqlalchemy.orm import Session
        from src.sqlalchemy_session_tracker import track_sqlalchemy_session
        
        # Store original session methods
        original_init = Session.__init__
        original_enter = Session.__enter__
        original_exit = Session.__exit__
        
        def tracked_init(self, *args, **kwargs):
            """Tracked session initialization"""
            original_init(self, *args, **kwargs)
            # Mark this session for tracking
            self._tracked = True
            
        def tracked_enter(self):
            """Tracked session enter"""
            if hasattr(self, '_tracked') and self._tracked:
                self._tracking_context = track_sqlalchemy_session(self, "auto_tracked_session")
                self._tracking_context.__enter__()
            return original_enter(self)
            
        def tracked_exit(self, exc_type, exc_val, exc_tb):
            """Tracked session exit"""
            try:
                result = original_exit(self, exc_type, exc_val, exc_tb)
                return result
            finally:
                if hasattr(self, '_tracking_context'):
                    try:
                        self._tracking_context.__exit__(exc_type, exc_val, exc_tb)
                    except:
                        pass
                    delattr(self, '_tracking_context')
        
        # Apply patches
        Session.__init__ = tracked_init
        Session.__enter__ = tracked_enter  
        Session.__exit__ = tracked_exit
        
        print("✅ SQLAlchemy session tracking enabled")
        
    except Exception as e:
        print(f"⚠️ Failed to patch SQLAlchemy: {e}")

def patch_flask_sqlalchemy():
    """Patch Flask-SQLAlchemy sessions specifically"""
    try:
        from flask_sqlalchemy import SQLAlchemy
        from src.sqlalchemy_session_tracker import track_sqlalchemy_session
        
        # Store original get method
        original_get = SQLAlchemy.session.get
        
        def tracked_get(self, *args, **kwargs):
            """Track Flask-SQLAlchemy session usage"""
            session = original_get(self, *args, **kwargs)
            if session:
                # Track this session
                try:
                    from src.sqlalchemy_session_tracker import track_sqlalchemy_session
                    context = track_sqlalchemy_session(session, "flask_sqlalchemy_session")
                    context.__enter__()
                    # Store context for cleanup
                    session._tracking_context = context
                except Exception:
                    pass
            return session
            
        SQLAlchemy.session.get = tracked_get
        
        print("✅ Flask-SQLAlchemy session tracking enabled")
        
    except Exception as e:
        print(f"⚠️ Failed to patch Flask-SQLAlchemy: {e}")

# Auto-patch on import
if __name__ != "__main__":
    patch_sqlalchemy_sessions()
    patch_flask_sqlalchemy()

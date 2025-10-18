"""
Connection Tracker - Track which routes/functions are using database connections
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List
from flask import request, has_request_context

# Global connection tracking
_connection_tracking = defaultdict(lambda: {
    'count': 0,
    'active': 0,
    'total_time': 0.0,
    'requests': []
})
_tracking_lock = threading.Lock()

def get_current_context():
    """Get current route/function context"""
    if has_request_context():
        return f"{request.method} {request.path}"
    else:
        # For background workers
        import inspect
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

def track_connection_acquired(context=None):
    """Track when a connection is acquired"""
    if context is None:
        context = get_current_context()
    
    with _tracking_lock:
        _connection_tracking[context]['count'] += 1
        _connection_tracking[context]['active'] += 1
        _connection_tracking[context]['requests'].append({
            'acquired_at': time.time(),
            'thread_id': threading.get_ident()
        })
    
    return context, time.time()

def track_connection_released(context, start_time):
    """Track when a connection is released"""
    duration = time.time() - start_time
    
    with _tracking_lock:
        if context in _connection_tracking:
            _connection_tracking[context]['active'] -= 1
            _connection_tracking[context]['total_time'] += duration
            
            # Remove from active requests
            _connection_tracking[context]['requests'] = [
                r for r in _connection_tracking[context]['requests']
                if r['acquired_at'] != start_time
            ]

def get_connection_stats() -> Dict:
    """Get connection usage statistics by route/function"""
    with _tracking_lock:
        stats = {}
        
        # Sort by active connections (descending)
        sorted_contexts = sorted(
            _connection_tracking.items(),
            key=lambda x: x[1]['active'],
            reverse=True
        )
        
        for context, data in sorted_contexts:
            if data['count'] > 0:  # Only show contexts that have used connections
                avg_time = data['total_time'] / data['count'] if data['count'] > 0 else 0
                
                stats[context] = {
                    'active_now': data['active'],
                    'total_acquired': data['count'],
                    'avg_duration_ms': round(avg_time * 1000, 2),
                    'active_requests': len(data['requests'])
                }
        
        return stats

def get_top_connection_users(limit=10) -> List[Dict]:
    """Get top N routes/functions by active connections"""
    stats = get_connection_stats()
    
    # Sort by active connections
    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1]['active_now'],
        reverse=True
    )[:limit]
    
    return [
        {
            'route': route,
            'active': data['active_now'],
            'total': data['total_acquired'],
            'avg_ms': data['avg_duration_ms']
        }
        for route, data in sorted_stats
    ]

def reset_tracking():
    """Reset all tracking data (for testing)"""
    with _tracking_lock:
        _connection_tracking.clear()


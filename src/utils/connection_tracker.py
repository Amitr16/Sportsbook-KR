"""
Connection Tracker - Track which routes/functions are using database connections
ENHANCED VERSION with proper acquire/release tracking and leak detection
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List
from flask import request, has_request_context

# Global connection tracking with enhanced counters
_connection_tracking = defaultdict(lambda: {
    'acquired': 0,      # Total connections acquired (lifetime)
    'released': 0,      # Total connections released (lifetime) 
    'active': 0,        # Currently active connections
    'total_time': 0.0,  # Total time spent with connections
    'requests': [],     # Active request tracking
    'leaks': 0          # Count of detected leaks
})
_tracking_lock = threading.Lock()

# Global counters for overall tracking
_global_stats = {
    'total_acquired': 0,
    'total_released': 0,
    'total_active': 0
}

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
        # Update per-context stats
        _connection_tracking[context]['acquired'] += 1
        _connection_tracking[context]['active'] += 1
        
        # Update global stats
        _global_stats['total_acquired'] += 1
        _global_stats['total_active'] += 1
        
        # Track this specific request
        request_id = f"{context}_{time.time()}_{threading.get_ident()}"
        _connection_tracking[context]['requests'].append({
            'request_id': request_id,
            'acquired_at': time.time(),
            'thread_id': threading.get_ident()
        })
    
    return context, time.time()

def track_connection_released(context, start_time):
    """Track when a connection is released"""
    duration = time.time() - start_time
    
    with _tracking_lock:
        if context in _connection_tracking:
            # Update per-context stats
            _connection_tracking[context]['released'] += 1
            _connection_tracking[context]['active'] = max(0, _connection_tracking[context]['active'] - 1)
            _connection_tracking[context]['total_time'] += duration
            
            # Update global stats
            _global_stats['total_released'] += 1
            _global_stats['total_active'] = max(0, _global_stats['total_active'] - 1)
            
            # Remove the oldest active request (FIFO)
            if _connection_tracking[context]['requests']:
                _connection_tracking[context]['requests'].pop(0)

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
            if data['acquired'] > 0:  # Only show contexts that have used connections
                avg_time = data['total_time'] / data['acquired'] if data['acquired'] > 0 else 0
                
                # Calculate leaks as acquired - released (should equal active)
                leaks = max(0, data['acquired'] - data['released'])
                
                stats[context] = {
                    'acquired': data['acquired'],
                    'released': data['released'],
                    'active': data['active'],
                    'leaks': leaks,
                    'avg_duration_ms': round(avg_time * 1000, 2),
                    'total_time': round(data['total_time'], 2),
                    'active_requests': len(data['requests'])
                }
        
        return stats

def get_top_connection_users(limit=10) -> List[Dict]:
    """Get top N routes/functions by active connections"""
    stats = get_connection_stats()
    
    # Sort by active connections
    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1]['active'],
        reverse=True
    )[:limit]
    
    return [
        {
            'route': route,
            'acquired': data['acquired'],
            'released': data['released'],
            'active': data['active'],
            'leaks': data['leaks'],
            'total': data['acquired'],  # For backward compatibility
            'avg_ms': data['avg_duration_ms']
        }
        for route, data in sorted_stats
    ]

def get_global_connection_stats() -> Dict:
    """Get global connection statistics"""
    with _tracking_lock:
        # Calculate total leaks by summing up all per-context leaks
        total_leaks = sum(data['leaks'] for data in _connection_tracking.values())
        
        return {
            'total_acquired': _global_stats['total_acquired'],
            'total_released': _global_stats['total_released'],
            'total_active': _global_stats['total_active'],
            'total_leaks': total_leaks,
            'leak_ratio': round(total_leaks / max(_global_stats['total_acquired'], 1) * 100, 2)
        }

def reset_tracking():
    """Reset all tracking data (for testing)"""
    with _tracking_lock:
        _connection_tracking.clear()
        _global_stats.update({
            'total_acquired': 0,
            'total_released': 0,
            'total_active': 0
        })


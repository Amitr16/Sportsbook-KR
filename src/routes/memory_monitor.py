# Memory monitoring endpoint
import os
from flask import Blueprint, jsonify

# Safe import of psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError as e:
    psutil = None
    PSUTIL_AVAILABLE = False
    PSUTIL_ERROR = str(e)

memory_bp = Blueprint('memory', __name__)

@memory_bp.route('/memory-status')
def memory_status():
    """Get current memory usage statistics"""
    if not PSUTIL_AVAILABLE:
        return jsonify({
            'error': f'psutil not available: {PSUTIL_ERROR}',
            'available': False
        }), 503
    
    try:
        # Get process memory info
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Get system memory info
        system_memory = psutil.virtual_memory()
        
        # Convert to MB
        process_rss_mb = memory_info.rss / (1024 * 1024)
        process_vms_mb = memory_info.vms / (1024 * 1024)
        system_total_mb = system_memory.total / (1024 * 1024)
        system_used_mb = system_memory.used / (1024 * 1024)
        system_available_mb = system_memory.available / (1024 * 1024)
        system_percent = system_memory.percent
        
        return jsonify({
            'process_memory': {
                'rss_mb': round(process_rss_mb, 2),
                'vms_mb': round(process_vms_mb, 2)
            },
            'system_memory': {
                'total_mb': round(system_total_mb, 2),
                'used_mb': round(system_used_mb, 2),
                'available_mb': round(system_available_mb, 2),
                'percent_used': round(system_percent, 2)
            },
            'memory_pressure': {
                'is_high': process_rss_mb > 1400,  # 1.4GB threshold
                'threshold_mb': 1400
            },
            'available': True
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@memory_bp.route('/memory-force-gc')
def force_garbage_collection():
    """Force garbage collection and return memory stats"""
    if not PSUTIL_AVAILABLE:
        return jsonify({
            'error': f'psutil not available: {PSUTIL_ERROR}',
            'available': False
        }), 503
    
    import gc
    
    try:
        # Get memory before GC
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / (1024 * 1024)
        
        # Force garbage collection
        collected = gc.collect()
        
        # Get memory after GC
        memory_after = process.memory_info().rss / (1024 * 1024)
        memory_freed = memory_before - memory_after
        
        return jsonify({
            'memory_before_mb': round(memory_before, 2),
            'memory_after_mb': round(memory_after, 2),
            'memory_freed_mb': round(memory_freed, 2),
            'objects_collected': collected,
            'available': True
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

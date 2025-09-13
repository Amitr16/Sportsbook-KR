# Memory monitoring utility
import os
import psutil
import time
import logging

logger = logging.getLogger(__name__)
proc = psutil.Process(os.getpid())

def log_mem(hint=""):
    """Log current memory usage"""
    rss = proc.memory_info().rss / (1024*1024)
    logger.info(f"[MEM] {hint} RSS={rss:.1f} MB")
    return rss

def check_memory_limit():
    """Check if memory usage exceeds soft limit"""
    rss_mb = proc.memory_info().rss / (1024*1024)
    soft_limit = int(os.getenv('MEM_SOFT_LIMIT_MB', '1400'))
    return rss_mb > soft_limit

def force_gc_if_needed():
    """Force garbage collection if memory is high"""
    if check_memory_limit():
        import gc
        logger.warning(f"[MEM] High memory usage detected, forcing GC")
        gc.collect()
        log_mem("after forced GC")

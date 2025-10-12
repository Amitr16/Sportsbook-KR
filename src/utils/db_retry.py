"""
Database retry utility for read-only endpoints

Use this ONLY for read endpoints where duplicates are harmless.
DO NOT use for write operations.
"""

import time
import random
from contextlib import contextmanager
from src.db_compat import connection_ctx
from psycopg_pool.errors import PoolTimeout
import logging

logger = logging.getLogger(__name__)

@contextmanager
def ro_connection_with_retry(attempts=2, timeout=5):
    """
    Read-only connection with retry on PoolTimeout.
    
    Args:
        attempts: Number of retry attempts (default: 2)
        timeout: Connection timeout in seconds (default: 5)
    
    Yields:
        Database connection
        
    Usage:
        with ro_connection_with_retry() as conn:
            # read-only DB operations
            cur = conn.cursor()
            cur.execute("SELECT ...")
    """
    for i in range(attempts):
        try:
            with connection_ctx() as conn:
                yield conn
                return
        except PoolTimeout as e:
            if i == attempts - 1:
                # Last attempt failed, propagate the error
                logger.error(f"❌ All {attempts} connection attempts failed: {e}")
                raise
            # Random jitter to avoid thundering herd
            jitter = 0.05 + random.random() * 0.15
            logger.warning(f"⚠️ Connection timeout (attempt {i + 1}/{attempts}), retrying in {jitter:.2f}s")
            time.sleep(jitter)


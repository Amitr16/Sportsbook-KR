"""
BULLETPROOF health check endpoint - completely DB-free
"""

from flask import Blueprint, jsonify
import time
import os

health_bp = Blueprint("health", __name__)

@health_bp.get("/health")
@health_bp.get("/healthz")  # Kubernetes-style endpoint
def health():
    """
    BULLETPROOF health check - NO DB, NO Redis, NO external dependencies
    
    Returns 200 even during DB outages to prevent VM flapping.
    This endpoint must NEVER import modules that initialize pools.
    """
    return jsonify({
        "ok": True, 
        "status": "healthy",
        "timestamp": time.time(),
        "version": os.getenv("APP_VERSION", "unknown")
    }), 200


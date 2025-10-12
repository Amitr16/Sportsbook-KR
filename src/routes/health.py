"""
Lightweight health check endpoint that doesn't depend on database
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.get("/health")
def health():
    """
    Lightweight health check that doesn't touch the database.
    
    This prevents transient DB hiccups from marking the entire instance
    as unhealthy and triggering unnecessary restarts.
    """
    return jsonify({"ok": True, "status": "healthy"}), 200


"""
Sports API Routes - Debug Version with Enhanced Logging
"""

from flask import Blueprint, jsonify, request
from src.goalserve_client import OptimizedGoalServeClient
import logging

logger = logging.getLogger(__name__)

sports_bp = Blueprint('sports', __name__)

# Initialize the optimized GoalServe client
goalserve_client = OptimizedGoalServeClient()

@sports_bp.route('/sports', methods=['GET'])
def get_sports():
    """
    Get all available sports with optimized loading
    """
    try:
        logger.info("=== SPORTS API CALLED (OPTIMIZED) ===")
        
        # Force clear cache to ensure we get fresh data
        goalserve_client.clear_cache()
        logger.info("Cache cleared, fetching fresh sports data...")
        
        # Use optimized sport discovery with caching
        sports = goalserve_client.get_available_sports()
        logger.info(f"Optimized sports data: {sports}")
        
        logger.info(f"=== RETURNING {len(sports)} SPORTS (CACHED) ===")
        return jsonify(sports)
        
    except Exception as e:
        logger.error(f"Error fetching sports: {e}")
        return jsonify([]), 500

@sports_bp.route('/sports/<sport_name>/events', methods=['GET'])
def get_sport_events(sport_name):
    """
    Get events for a specific sport with optimized loading
    """
    try:
        # Get query parameters
        date_filter = request.args.get('date', 'all')
        limit = int(request.args.get('limit', 50))
        
        logger.info(f"=== EVENTS API CALLED (OPTIMIZED) ===")
        logger.info(f"Sport: {sport_name}, Date: {date_filter}, Limit: {limit}")
        
        # Use optimized event fetching with caching
        events = goalserve_client.get_sport_events(sport_name, date_filter, limit)
        logger.info(f"Optimized events returned: {len(events) if events else 0}")
        
        logger.info(f"=== RETURNING {len(events)} CACHED EVENTS ===")
        return jsonify(events)
        
    except Exception as e:
        logger.error(f"Error fetching events for {sport_name}: {e}")
        logger.exception("Full exception details:")
        return jsonify([]), 500

@sports_bp.route('/sports/clear-cache', methods=['POST'])
def clear_cache():
    """
    Clear the GoalServe client cache
    """
    try:
        logger.info("=== CACHE CLEAR API CALLED ===")
        goalserve_client.clear_cache()
        
        # Get cache stats after clearing
        cache_stats = goalserve_client.get_cache_stats()
        
        logger.info(f"Cache cleared successfully. Stats: {cache_stats}")
        return jsonify({
            'status': 'success',
            'message': 'Cache cleared successfully',
            'cache_stats': cache_stats
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500



@sports_bp.route('/sports/health', methods=['GET'])
def health_check():
    """
    Check GoalServe API health and capabilities
    """
    try:
        health_data = goalserve_client.health_check()
        return jsonify(health_data)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sports_bp.route('/<sport_name>', methods=['GET'])
def get_sport_data(sport_name):
    """
    Get all data for a specific sport (events, odds, etc.)
    """
    try:
        # Get query parameters
        date_filter = request.args.get('date', 'all')
        limit = int(request.args.get('limit', 50))
        
        logger.info(f"=== SPORT DATA API CALLED ===")
        logger.info(f"Sport: {sport_name}, Date: {date_filter}, Limit: {limit}")
        
        # Use optimized event fetching with caching
        events = goalserve_client.get_sport_events(sport_name, date_filter, limit)
        logger.info(f"Optimized events returned: {len(events) if events else 0}")
        
        logger.info(f"=== RETURNING {len(events)} EVENTS ===")
        return jsonify(events)
        
    except Exception as e:
        logger.error(f"Error fetching data for {sport_name}: {e}")
        logger.exception("Full exception details:")
        return jsonify([]), 500

@sports_bp.route('/<sport_name>/odds', methods=['GET'])
def get_live_odds(sport_name):
    """
    Get live odds for a sport with automatic market detection
    """
    try:
        logger.info(f"Fetching live odds for {sport_name}")
        
        odds_data = goalserve_client.get_live_odds(sport_name)
        
        logger.info(f"Successfully fetched odds for {len(odds_data)} matches")
        return jsonify(odds_data)
        
    except Exception as e:
        logger.error(f"Error fetching odds for {sport_name}: {e}")
        return jsonify([]), 500


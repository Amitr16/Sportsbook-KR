"""
Public APIs for non-authenticated users to view sports data
"""

from flask import Blueprint, request, jsonify
from src.db_compat import connection_ctx
import os
import json
import logging

logger = logging.getLogger(__name__)

public_apis_bp = Blueprint('public_apis', __name__)

@public_apis_bp.route('/api/public/sports', methods=['GET'])
def get_public_sports():
    """Get available sports for public viewing"""
    try:
        # Path to Sports Pre Match directory
        sports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Sports Pre Match')
        
        if not os.path.exists(sports_dir):
            return jsonify({'sports': []})
        
        sports = []
        for item in os.listdir(sports_dir):
            item_path = os.path.join(sports_dir, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                # Check if directory has JSON files
                json_files = [f for f in os.listdir(item_path) if f.endswith('.json')]
                if json_files:
                    sports.append({
                        'name': item.replace('_', ' ').title(),
                        'key': item,
                        'event_count': len(json_files)
                    })
        
        return jsonify({'sports': sports})
        
    except Exception as e:
        logger.error(f"Error getting public sports: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_apis_bp.route('/api/public/sports/<sport>/events', methods=['GET'])
def get_public_sport_events(sport):
    """Get events for a specific sport for public viewing"""
    try:
        # Path to sport directory
        sport_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Sports Pre Match', sport)
        
        if not os.path.exists(sport_dir):
            return jsonify({'events': []})
        
        events = []
        for filename in os.listdir(sport_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(sport_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            events.extend(data)
                        elif isinstance(data, dict) and 'events' in data:
                            events.extend(data['events'])
                except Exception as e:
                    logger.warning(f"Error reading {filename}: {e}")
                    continue
        
        return jsonify({'events': events})
        
    except Exception as e:
        logger.error(f"Error getting public sport events: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_apis_bp.route('/api/public/events', methods=['GET'])
def get_public_events():
    """Get all events across all sports for public viewing"""
    try:
        # Path to Sports Pre Match directory
        sports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Sports Pre Match')
        
        if not os.path.exists(sports_dir):
            return jsonify({'events': []})
        
        all_events = []
        for sport in os.listdir(sports_dir):
            sport_path = os.path.join(sports_dir, sport)
            if os.path.isdir(sport_path) and not sport.startswith('.'):
                for filename in os.listdir(sport_path):
                    if filename.endswith('.json'):
                        file_path = os.path.join(sport_path, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    for event in data:
                                        event['sport'] = sport
                                        all_events.append(event)
                                elif isinstance(data, dict) and 'events' in data:
                                    for event in data['events']:
                                        event['sport'] = sport
                                        all_events.append(event)
                        except Exception as e:
                            logger.warning(f"Error reading {sport}/{filename}: {e}")
                            continue
        
        return jsonify({'events': all_events})
        
    except Exception as e:
        logger.error(f"Error getting public events: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_apis_bp.route('/api/public/odds/<event_id>', methods=['GET'])
def get_public_event_odds(event_id):
    """Get odds for a specific event for public viewing"""
    try:
        # This would typically query the database for odds
        # For now, return a placeholder response
        return jsonify({
            'event_id': event_id,
            'odds': [],
            'message': 'Odds data not available for public viewing'
        })
        
    except Exception as e:
        logger.error(f"Error getting public event odds: {e}")
        return jsonify({'error': 'Internal server error'}), 500

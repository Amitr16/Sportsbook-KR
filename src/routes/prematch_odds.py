"""
Pre-match odds service API routes
"""

from flask import Blueprint, jsonify, request
from src.prematch_odds_service import get_prematch_odds_service
import logging

logger = logging.getLogger(__name__)

prematch_odds_bp = Blueprint('prematch_odds', __name__)

@prematch_odds_bp.route('/status', methods=['GET'])
def get_prematch_odds_status():
    """Get pre-match odds service status"""
    try:
        service = get_prematch_odds_service()
        stats = service.get_stats()
        
        return jsonify({
            'success': True,
            'service_running': stats['service_running'],
            'total_sports': stats['total_sports'],
            'stats': stats['stats'],
            'base_folder': stats['base_folder'],
            'sports_configured': stats['sports_configured']
        })
        
    except Exception as e:
        logger.error(f"Error getting pre-match odds status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/start', methods=['POST'])
def start_prematch_odds_service():
    """Start the pre-match odds service"""
    try:
        service = get_prematch_odds_service()
        
        if service.running:
            return jsonify({
                'success': True,
                'message': 'Service is already running',
                'service_running': True
            })
        
        success = service.start()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Pre-match odds service started successfully',
                'service_running': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start pre-match odds service'
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting pre-match odds service: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/stop', methods=['POST'])
def stop_prematch_odds_service():
    """Stop the pre-match odds service"""
    try:
        service = get_prematch_odds_service()
        
        if not service.running:
            return jsonify({
                'success': True,
                'message': 'Service is already stopped',
                'service_running': False
            })
        
        service.stop()
        
        return jsonify({
            'success': True,
            'message': 'Pre-match odds service stopped successfully',
            'service_running': False
        })
        
    except Exception as e:
        logger.error(f"Error stopping pre-match odds service: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/fetch-now', methods=['POST'])
def fetch_odds_now():
    """Trigger an immediate odds fetch for all sports"""
    try:
        service = get_prematch_odds_service()
        
        # Get request parameters
        data = request.get_json() or {}
        sport_name = data.get('sport')  # Optional: fetch specific sport only
        
        if sport_name:
            # Fetch single sport
            if sport_name not in service.sports_config:
                return jsonify({
                    'success': False,
                    'error': f'Unknown sport: {sport_name}'
                }), 400
            
            success = service._fetch_single_sport_odds(sport_name)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Successfully fetched odds for {sport_name}',
                    'sport': sport_name
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to fetch odds for {sport_name}'
                }), 500
        else:
            # Fetch all sports
            service._fetch_all_sports_odds()
            
            return jsonify({
                'success': True,
                'message': 'Successfully triggered odds fetch for all sports'
            })
            
    except Exception as e:
        logger.error(f"Error fetching odds now: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/files', methods=['GET'])
def get_recent_files():
    """Get recent odds files"""
    try:
        service = get_prematch_odds_service()
        
        # Get query parameters
        sport_name = request.args.get('sport')
        limit = int(request.args.get('limit', 10))
        
        files = service.get_recent_files(sport_name=sport_name, limit=limit)
        
        return jsonify({
            'success': True,
            'files': files,
            'total_files': len(files)
        })
        
    except Exception as e:
        logger.error(f"Error getting recent files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/sports', methods=['GET'])
def get_configured_sports():
    """Get list of configured sports"""
    try:
        service = get_prematch_odds_service()
        
        sports_info = []
        for sport_name, config in service.sports_config.items():
            sports_info.append({
                'name': sport_name,
                'display_name': config['display_name'],
                'icon': config['icon'],
                'category': config['category']
            })
        
        return jsonify({
            'success': True,
            'sports': sports_info,
            'total_sports': len(sports_info)
        })
        
    except Exception as e:
        logger.error(f"Error getting configured sports: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/test-url/<sport_name>', methods=['GET'])
def test_odds_url(sport_name):
    """Test the odds URL for a specific sport"""
    try:
        service = get_prematch_odds_service()
        
        if sport_name not in service.sports_config:
            return jsonify({
                'success': False,
                'error': f'Unknown sport: {sport_name}'
            }), 400
        
        # Get dynamic dates
        date_start, date_end = service._get_dynamic_dates()
        
        # Build URL
        url = service._build_odds_url(sport_name, date_start, date_end)
        
        return jsonify({
            'success': True,
            'sport': sport_name,
            'url': url,
            'date_start': date_start,
            'date_end': date_end,
            'category': service.sports_config[sport_name]['category']
        })
        
    except Exception as e:
        logger.error(f"Error testing odds URL: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prematch_odds_bp.route('/file-content', methods=['GET'])
def get_file_content():
    """Get the content of a specific odds file"""
    try:
        import json
        from pathlib import Path
        
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'File path is required'
            }), 400
        
        # Security check - ensure the path is within the base folder
        service = get_prematch_odds_service()
        base_folder = service.base_folder
        
        # Convert to Path objects for comparison
        requested_path = Path(file_path)
        if not requested_path.is_relative_to(base_folder):
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        if not requested_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Read and return the file content
        with open(requested_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        return jsonify({
            'success': True,
            'content': content
        })
        
    except Exception as e:
        logger.error(f"Error reading file content: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

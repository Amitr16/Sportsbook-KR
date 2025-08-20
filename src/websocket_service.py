import threading
import time
from flask_socketio import SocketIO, emit
from src.goalserve_client import OptimizedGoalServeClient
import logging

logger = logging.getLogger(__name__)

class LiveOddsWebSocketService:
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.client = OptimizedGoalServeClient()
        self.running = False
        self.update_thread = None
        self.update_interval = 2  # Update every 2 seconds for real-time experience
        self.critical_matches = set()  # Track matches in critical moments
        
    def start(self):
        """Start the live odds update service"""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
            logger.info("Live odds WebSocket service started")
    
    def stop(self):
        """Stop the live odds update service"""
        self.running = False
        if self.update_thread:
            self.update_thread.join()
        logger.info("Live odds WebSocket service stopped")
    
    def _update_loop(self):
        """Main update loop that fetches and broadcasts live odds"""
        while self.running:
            try:
                # Fetch live odds for soccer
                live_odds = self.client.get_live_odds('soccer')
                
                if live_odds:
                    # Check for critical matches (last 10 minutes or close score)
                    current_critical_matches = set()
                    for match in live_odds:
                        if match.get('live_odds'):
                            time_remaining = match['live_odds'].get('time_remaining', 0)
                            match_progress = match['live_odds'].get('match_progress', 0)
                            
                            # Critical if last 10 minutes or close score in last 20 minutes
                            if (time_remaining <= 10) or (match_progress >= 0.75 and time_remaining <= 20):
                                current_critical_matches.add(f"{match['home_team']} vs {match['away_team']}")
                    
                    # Update critical matches tracking
                    if current_critical_matches != self.critical_matches:
                        if current_critical_matches:
                            logger.info(f"Critical matches detected: {', '.join(current_critical_matches)}")
                        self.critical_matches = current_critical_matches
                    
                    # Broadcast live odds to all connected clients
                    self.socketio.emit('live_odds_update', {
                        'sport': 'soccer',
                        'odds': live_odds,
                        'timestamp': time.time(),
                        'critical_matches': list(current_critical_matches)
                    })
                    
                    # Log update frequency based on critical matches
                    if current_critical_matches:
                        logger.info(f"Broadcasted {len(live_odds)} live odds updates (including {len(current_critical_matches)} critical matches)")
                    else:
                        logger.info(f"Broadcasted {len(live_odds)} live odds updates")
                else:
                    logger.debug("No live odds available")
                    
            except Exception as e:
                logger.error(f"Error in live odds update loop: {e}")
            
            # Dynamic update interval: faster for critical matches
            if self.critical_matches:
                sleep_time = 1  # 1 second for critical matches
            else:
                sleep_time = self.update_interval  # 2 seconds for normal matches
            
            time.sleep(sleep_time)
    
    def get_connected_clients_count(self):
        """Get the number of connected WebSocket clients"""
        return len(self.socketio.server.manager.rooms.get('/', {}))
    
    def broadcast_specific_match_update(self, match_id: str, odds_data: dict):
        """Broadcast update for a specific match"""
        self.socketio.emit('match_odds_update', {
            'match_id': match_id,
            'odds': odds_data,
            'timestamp': time.time()
        })
        logger.info(f"Broadcasted specific match update for {match_id}")
    
    def get_critical_matches(self):
        """Get list of matches in critical moments"""
        return list(self.critical_matches)

# WebSocket event handlers
def init_websocket_handlers(socketio: SocketIO, live_odds_service: LiveOddsWebSocketService):
    """Initialize WebSocket event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info(f"Client connected. Total clients: {live_odds_service.get_connected_clients_count()}")
        emit('connection_status', {'status': 'connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        logger.info(f"Client disconnected. Total clients: {live_odds_service.get_connected_clients_count()}")
    
    @socketio.on('subscribe_live_odds')
    def handle_subscribe_live_odds(data):
        """Handle live odds subscription"""
        sport = data.get('sport', 'soccer')
        logger.info(f"Client subscribed to live odds for {sport}")
        emit('subscription_confirmed', {'sport': sport, 'status': 'subscribed'})
    
    @socketio.on('request_live_odds')
    def handle_request_live_odds(data):
        """Handle immediate live odds request"""
        try:
            sport = data.get('sport', 'soccer')
            live_odds = live_odds_service.client.get_live_odds(sport)
            emit('live_odds_response', {
                'sport': sport,
                'odds': live_odds,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error handling live odds request: {e}")
            emit('error', {'message': 'Failed to fetch live odds'}) 
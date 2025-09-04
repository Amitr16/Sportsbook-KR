#!/usr/bin/env python3
"""
GoalServe Sports Betting Platform - FastAPI Edition
Main application entry point for both local and Fly.io deployment
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
from contextlib import asynccontextmanager

# Import settings
from src.settings import settings

# Import services
from src.bet_settlement_service import BetSettlementService
from src.websocket_service import LiveOddsWebSocketService, init_websocket_handlers

# Global services
bet_settlement_service = None
live_odds_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global bet_settlement_service, live_odds_service
    
    # Startup
    print("🚀 Starting GoalServe Sports Betting Platform - FastAPI Edition")
    print(f"📍 Environment: {settings.ENV}")
    print(f"📍 Server: http://{settings.HOST}:{settings.PORT}")
    print(f"📍 Database: {settings.DATABASE_TYPE}")
    print(f"📍 Redis: {settings.REDIS_URL}")
    
    # Initialize services
    try:
        # Initialize bet settlement service
        bet_settlement_service = BetSettlementService()
        bet_settlement_service.start()
        print("✅ Bet settlement service started")
        
        # Initialize WebSocket service
        live_odds_service = LiveOddsWebSocketService()
        live_odds_service.start()
        print("✅ Live odds WebSocket service started")
        
    except Exception as e:
        print(f"❌ Error starting services: {e}")
        raise
    
    yield
    
    # Shutdown
    print("🛑 Shutting down services...")
    if bet_settlement_service:
        bet_settlement_service.stop()
    if live_odds_service:
        live_odds_service.stop()
    print("✅ Services stopped gracefully")

# Create FastAPI app
app = FastAPI(
    title="GoalServe Sports Betting Platform",
    description="Future-Proof Sports Betting Platform with Real-Time Updates",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Socket.IO
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.SOCKET_ALLOWED_ORIGINS,
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Initialize WebSocket handlers
init_websocket_handlers(sio)

# Create ASGI app with Socket.IO
asgi = socketio.ASGIApp(
    sio, 
    other_asgi_app=app, 
    socketio_path=settings.SOCKETIO_PATH
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Also serve static files at root level for compatibility
@app.get("/static/{path:path}")
async def serve_static_files(path: str):
    """Serve static files from /static/ path"""
    static_file = f"src/static/{path}"
    if os.path.exists(static_file):
        return FileResponse(static_file)
    else:
        return {"error": "File not found"}, 404

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENV,
        "database": settings.DATABASE_TYPE,
        "redis": "connected" if settings.REDIS_URL else "not configured"
    }

# WebSocket health check endpoint
@app.get("/ws-health")
async def websocket_health_check():
    """Check WebSocket service health"""
    try:
        if live_odds_service:
            ws_status = "running" if live_odds_service.running else "stopped"
            connected_clients = live_odds_service.get_connected_clients_count()
            
            return {
                'status': 'healthy',
                'websocket_service': ws_status,
                'connected_clients': connected_clients
            }
        else:
            return {
                'status': 'error',
                'error': 'WebSocket service not initialized'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

# Static file serving routes
@app.get("/")
async def serve_index():
    """Serve the main index page"""
    return FileResponse("src/static/index.html")

@app.get("/login")
async def serve_login():
    """Serve the login page"""
    return FileResponse("src/static/login.html")

@app.get("/register-sportsbook")
async def serve_register_sportsbook():
    """Serve the sportsbook registration page"""
    return FileResponse("src/static/register-sportsbook.html")

@app.get("/admin-login")
async def serve_admin_login():
    """Serve the admin login page"""
    return FileResponse("src/static/admin-login.html")

@app.get("/admin-dashboard")
async def serve_admin_dashboard():
    """Serve the admin dashboard page"""
    return FileResponse("src/static/admin-dashboard.html")

# Catch-all route for other static files
@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve other static files"""
    static_file = f"src/static/{path}"
    if os.path.exists(static_file):
        return FileResponse(static_file)
    else:
        # Fallback to index.html for SPA routing
        return FileResponse("src/static/index.html")

# Import and register API routes
from src.routes import auth, betting, sports, prematch_odds, json_sports

app.include_router(auth.auth_bp, prefix="/api")
app.include_router(betting.betting_bp, prefix="/api")
app.include_router(sports.sports_bp, prefix="/api")
app.include_router(prematch_odds.prematch_odds_bp, prefix="/api")
app.include_router(json_sports.json_sports_bp, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main_fastapi:asgi",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

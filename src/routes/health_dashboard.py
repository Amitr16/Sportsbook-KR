"""
Health Dashboard - Visual display of system health metrics
"""
from flask import Blueprint, render_template_string, jsonify
import requests
import os

health_dashboard_bp = Blueprint('health_dashboard', __name__)

HEALTH_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Health Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .header .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .last-updated {
            text-align: center;
            color: white;
            margin-bottom: 20px;
            font-size: 0.9rem;
            opacity: 0.8;
        }
        
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }
        
        .card-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: #2d3748;
        }
        
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-healthy {
            background: #d4edda;
            color: #155724;
        }
        
        .status-degraded {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-unhealthy {
            background: #f8d7da;
            color: #721c24;
        }
        
        .metric {
            margin: 12px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .metric-label {
            color: #718096;
            font-size: 0.9rem;
        }
        
        .metric-value {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2d3748;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        
        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
            border-radius: 4px;
        }
        
        .progress-healthy {
            background: linear-gradient(90deg, #48bb78, #38a169);
        }
        
        .progress-warning {
            background: linear-gradient(90deg, #ed8936, #dd6b20);
        }
        
        .progress-critical {
            background: linear-gradient(90deg, #f56565, #e53e3e);
        }
        
        .overall-status {
            background: white;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .overall-status-icon {
            font-size: 4rem;
            margin-bottom: 10px;
        }
        
        .overall-status-text {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .loading {
            text-align: center;
            color: white;
            font-size: 1.2rem;
            padding: 40px;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        
        .refresh-button {
            background: white;
            color: #667eea;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s;
        }
        
        .refresh-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        
        .auto-refresh {
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 0.9rem;
        }
        
        .auto-refresh input {
            margin-left: 8px;
            transform: scale(1.2);
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 System Health Dashboard</h1>
            <div class="subtitle">Real-time monitoring of Goalserve Sportsbook Backend</div>
        </div>
        
        <div id="loading" class="loading">
            Loading health data...
        </div>
        
        <div id="dashboard" style="display: none;">
            <div class="last-updated">
                Last updated: <span id="lastUpdate">-</span>
                <button class="refresh-button" onclick="loadHealth()" style="margin-left: 20px;">🔄 Refresh Now</button>
            </div>
            
            <div class="overall-status" id="overallStatus">
                <div class="overall-status-icon" id="overallIcon">-</div>
                <div class="overall-status-text" id="overallText">-</div>
                <div id="overallSubtext" style="color: #718096; font-size: 1rem;">-</div>
            </div>
            
            <div class="cards-grid">
                <!-- Database Pool Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">💾 Database Pool</div>
                        <div class="status-badge" id="dbStatus">-</div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Active Connections</span>
                        <span class="metric-value" id="dbActive">-</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Max Connections</span>
                        <span class="metric-value" id="dbMax">-</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Usage</span>
                        <span class="metric-value" id="dbUsage">-</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="dbProgress" style="width: 0%"></div>
                    </div>
                    <div class="metric" style="margin-top: 16px;">
                        <span class="metric-label">Circuit Breaker</span>
                        <span class="metric-value" id="dbCircuit">-</span>
                    </div>
                    <div class="metric" style="margin-top: 8px;">
                        <span class="metric-label">SQLAlchemy Sessions</span>
                        <span class="metric-value" id="dbSqlAlchemy">-</span>
                    </div>
                    <div class="metric" style="margin-top: 8px;">
                        <span class="metric-label">Pool Sockets (Open)</span>
                        <span class="metric-value" id="dbPoolSize">-</span>
                    </div>
                    <div class="metric" style="margin-top: 8px;">
                        <span class="metric-label">Leaked & Recovered</span>
                        <span class="metric-value" id="dbLeakedRecovered">-</span>
                    </div>
                </div>
                
                <!-- Redis Cache Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🔴 Redis Cache</div>
                        <div class="status-badge" id="redisStatus">-</div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Connection</span>
                        <span class="metric-value" id="redisConn">-</span>
                    </div>
                </div>
                
                <!-- Redis Sessions Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🔐 Redis Sessions</div>
                        <div class="status-badge" id="sessionsStatus">-</div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Redis Available</span>
                        <span class="metric-value" id="sessionsAvailable">-</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Active Sessions</span>
                        <span class="metric-value" id="sessionCount">-</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Prefix</span>
                        <span class="metric-value" id="sessionPrefix">-</span>
                    </div>
                </div>
            </div>
            
            <!-- Connection Tracking Section -->
            <div style="margin-top: 30px;">
                <div class="card" style="grid-column: 1 / -1;">
                    <div class="card-header">
                        <div class="card-title">🔍 Connection Usage by Route/Function</div>
                        <button onclick="loadHealth()" style="padding: 8px 16px; border: none; background: #667eea; color: white; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500;">↻ Refresh Now</button>
                    </div>
                    <div style="overflow-x: auto; margin-top: 16px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #f7fafc; border-bottom: 2px solid #e2e8f0;">
                                    <th style="padding: 12px; text-align: left; font-weight: 600; color: #2d3748; font-size: 0.9rem;">Route/Function</th>
                                    <th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748; font-size: 0.9rem;">Active Now</th>
                                    <th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748; font-size: 0.9rem;">Total Acquired</th>
                                    <th style="padding: 12px; text-align: center; font-weight: 600; color: #2d3748; font-size: 0.9rem;">Avg Duration (ms)</th>
                                </tr>
                            </thead>
                            <tbody id="connectionTrackingBody">
                                <tr><td colspan="4" style="text-align: center; padding: 20px; color: #a0aec0;">Loading...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div style="margin-top: 16px; padding: 12px; background: #edf2f7; border-radius: 8px; font-size: 0.85rem; color: #2d3748; border-left: 4px solid #667eea;">
                        <strong style="color: #667eea;">💡 Debugging Guide:</strong><br>
                        • <strong style="color: #c53030;">Active Now > 0</strong> = Route is currently holding connections (potential leak!)<br>
                        • <strong style="color: #d69e2e;">Avg Duration > 300ms</strong> = Slow queries or missing statement_timeout<br>
                        • <strong style="color: #3182ce;">High Total count</strong> = Frequently called route (optimize if needed)
                    </div>
                </div>
            </div>
            
            <div class="auto-refresh">
                <label>
                    <input type="checkbox" id="autoRefresh" checked> 
                    Auto-refresh every 5 seconds
                </label>
            </div>
        </div>
        
        <div id="error" class="error" style="display: none;"></div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        
        function formatTimestamp(timestamp) {
            return new Date(timestamp * 1000).toLocaleString();
        }
        
        function getStatusClass(status) {
            if (status === 'healthy') return 'status-healthy';
            if (status === 'degraded') return 'status-degraded';
            return 'status-unhealthy';
        }
        
        function getProgressClass(percent) {
            if (percent < 50) return 'progress-healthy';
            if (percent < 80) return 'progress-warning';
            return 'progress-critical';
        }
        
        async function loadHealth() {
            try {
                const response = await fetch('/health/detailed');
                const data = await response.json();
                
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                document.getElementById('error').style.display = 'none';
                
                // Update timestamp
                document.getElementById('lastUpdate').textContent = formatTimestamp(data.timestamp);
                
                // Overall status
                const overallHealthy = data.ok;
                document.getElementById('overallIcon').textContent = overallHealthy ? '✅' : '❌';
                document.getElementById('overallText').textContent = overallHealthy ? 'All Systems Operational' : 'System Issues Detected';
                document.getElementById('overallText').style.color = overallHealthy ? '#38a169' : '#e53e3e';
                document.getElementById('overallSubtext').textContent = `Status: ${data.status}`;
                
                // Database Pool
                const db = data.checks.database_pool;
                document.getElementById('dbStatus').textContent = db.status;
                document.getElementById('dbStatus').className = 'status-badge ' + getStatusClass(db.status);
                document.getElementById('dbActive').textContent = db.checked_out;
                document.getElementById('dbMax').textContent = db.max_connections;
                document.getElementById('dbUsage').textContent = db.usage_percent.toFixed(1) + '%';
                document.getElementById('dbProgress').style.width = db.usage_percent + '%';
                document.getElementById('dbProgress').className = 'progress-fill ' + getProgressClass(db.usage_percent);
                document.getElementById('dbCircuit').textContent = db.circuit_breaker_open ? '🔴 OPEN' : '🟢 CLOSED';
                document.getElementById('dbCircuit').style.color = db.circuit_breaker_open ? '#e53e3e' : '#38a169';
                document.getElementById('dbSqlAlchemy').textContent = `${db.sqlalchemy_sessions || 0} active`;
                document.getElementById('dbPoolSize').textContent = `${db.pool_size || 0} sockets`;
                const leakedCount = db.leaked_recovered || 0;
                document.getElementById('dbLeakedRecovered').textContent = leakedCount;
                document.getElementById('dbLeakedRecovered').style.color = leakedCount > 0 ? '#e53e3e' : '#38a169';
                
                // Connection Tracking Table
                if (db.top_connection_users && db.top_connection_users.length > 0) {
                    const tbody = document.getElementById('connectionTrackingBody');
                    tbody.innerHTML = db.top_connection_users.map(user => `
                        <tr style="border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px; font-family: monospace; font-size: 0.9rem;">${user.route}</td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="display: inline-block; padding: 4px 8px; background: ${user.active > 0 ? '#fed7d7' : '#c6f6d5'}; color: ${user.active > 0 ? '#c53030' : '#22543d'}; border-radius: 4px; font-weight: 600;">
                                    ${user.active}
                                </span>
                            </td>
                            <td style="padding: 12px; text-align: center; color: #4a5568;">${user.total}</td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="color: ${user.avg_ms > 300 ? '#c53030' : '#2d3748'}; font-weight: ${user.avg_ms > 300 ? '600' : '400'};">
                                    ${user.avg_ms.toFixed(1)}
                                </span>
                            </td>
                        </tr>
                    `).join('');
                } else {
                    document.getElementById('connectionTrackingBody').innerHTML = 
                        '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #a0aec0;">No connection activity tracked yet</td></tr>';
                }
                
                // Redis Cache
                const redis = data.checks.redis;
                document.getElementById('redisStatus').textContent = redis.status;
                document.getElementById('redisStatus').className = 'status-badge ' + getStatusClass(redis.status);
                document.getElementById('redisConn').textContent = redis.status === 'healthy' ? '🟢 Connected' : '🔴 Disconnected';
                document.getElementById('redisConn').style.color = redis.status === 'healthy' ? '#38a169' : '#e53e3e';
                
                // Redis Sessions
                const sessions = data.checks.redis_sessions;
                if (!sessions || sessions.error) {
                    document.getElementById('sessionsStatus').textContent = 'error';
                    document.getElementById('sessionsStatus').className = 'status-badge status-unhealthy';
                    document.getElementById('sessionsAvailable').textContent = sessions && sessions.error ? '❌ ' + sessions.error : '❌ Not configured';
                    document.getElementById('sessionCount').textContent = '-';
                    document.getElementById('sessionPrefix').textContent = '-';
                } else {
                    document.getElementById('sessionsStatus').textContent = 'healthy';
                    document.getElementById('sessionsStatus').className = 'status-badge status-healthy';
                    document.getElementById('sessionsAvailable').textContent = sessions.redis_available ? '✅ Yes' : '❌ No';
                    document.getElementById('sessionsAvailable').style.color = sessions.redis_available ? '#38a169' : '#e53e3e';
                    document.getElementById('sessionCount').textContent = sessions.total_sessions || 0;
                    document.getElementById('sessionPrefix').textContent = sessions.prefix || '-';
                }
                
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = '❌ Error loading health data: ' + error.message;
            }
        }
        
        // Auto-refresh logic
        document.addEventListener('DOMContentLoaded', () => {
            loadHealth();
            
            const checkbox = document.getElementById('autoRefresh');
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    autoRefreshInterval = setInterval(loadHealth, 5000);
                } else {
                    if (autoRefreshInterval) {
                        clearInterval(autoRefreshInterval);
                        autoRefreshInterval = null;
                    }
                }
            });
            
            // Start auto-refresh
            autoRefreshInterval = setInterval(loadHealth, 5000);
        });
    </script>
</head>
<body>
</body>
</html>
"""

@health_dashboard_bp.route('/health/dashboard')
def health_dashboard():
    """Display visual health dashboard"""
    return render_template_string(HEALTH_DASHBOARD_HTML)


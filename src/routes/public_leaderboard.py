"""
Public Leaderboard Routes - No Authentication Required
"""

from flask import Blueprint, jsonify, request
from src import sqlite3_shim as sqlite3
import logging

logger = logging.getLogger(__name__)

public_leaderboard_bp = Blueprint('public_leaderboard', __name__)

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim"""
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    return conn

def get_latest_contest_end_date():
    """Get the latest contest end date from contest_dates table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT contest_end_date 
            FROM contest_dates 
            WHERE is_active = TRUE 
            ORDER BY contest_end_date DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Return the datetime as ISO format with Z suffix to indicate UTC
            return result[0].isoformat() + 'Z' if hasattr(result[0], 'isoformat') else str(result[0]) + 'Z'
        return None
        
    except Exception as e:
        logger.error(f"Error fetching contest end date: {e}")
        return None

@public_leaderboard_bp.route('/api/public/user-leaderboard')
def get_user_leaderboard():
    """Get user leaderboard ranked by profit - PUBLIC ACCESS"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total count of users (same as the leaderboard query)
        # First, get the exact same query as the leaderboard to count users
        cursor.execute("""
            SELECT 
                u.id
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            GROUP BY u.id, u.username, u.email
        """)
        all_users = cursor.fetchall()
        total_users = len(all_users)
        
        # Get user leaderboard data with profit calculation (only settled bets)
        # Show delta from backup table if available
        cursor.execute("""
            SELECT 
                u.username,
                u.email,
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as current_staked,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) as current_payout,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) - 
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as current_profit,
                COALESCE(ub.staked, 0) as backup_staked,
                COALESCE(ub.payout, 0) as backup_payout,
                COALESCE(ub.profit, 0) as backup_profit
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            LEFT JOIN (
                SELECT username, staked, payout, profit
                FROM User_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM User_leader_backup)
            ) ub ON u.username = ub.username
            GROUP BY u.id, u.username, u.email, ub.staked, ub.payout, ub.profit
            ORDER BY (COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) - 
                     COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0)) - 
                     COALESCE(ub.profit, 0) DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        users = []
        for row in cursor.fetchall():
            # Calculate deltas from backup
            current_staked = float(row[2])
            current_payout = float(row[3])
            current_profit = float(row[4])
            backup_staked = float(row[5])
            backup_payout = float(row[6])
            backup_profit = float(row[7])
            
            # Calculate deltas (current - backup)
            staked_delta = current_staked - backup_staked
            payout_delta = current_payout - backup_payout
            profit_delta = current_profit - backup_profit
            
            users.append({
                'username': row[0],
                'email': row[1],
                'staked': staked_delta,  # Show delta instead of absolute
                'payout': payout_delta,  # Show delta instead of absolute
                'profit': profit_delta,  # Show delta instead of absolute
                'backup_staked': backup_staked,
                'backup_payout': backup_payout,
                'backup_profit': backup_profit
            })
        
        # Get total statistics (only settled bets) - calculate deltas
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as current_total_staked,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) as current_total_payout,
                COALESCE(SUM(ub.staked), 0) as backup_total_staked,
                COALESCE(SUM(ub.payout), 0) as backup_total_payout
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            LEFT JOIN (
                SELECT username, staked, payout
                FROM User_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM User_leader_backup)
            ) ub ON u.username = ub.username
        """)
        
        stats_row = cursor.fetchone()
        current_total_staked = float(stats_row[0])
        current_total_payout = float(stats_row[1])
        backup_total_staked = float(stats_row[2])
        backup_total_payout = float(stats_row[3])
        
        # Calculate deltas
        total_staked_delta = current_total_staked - backup_total_staked
        total_payout_delta = current_total_payout - backup_total_payout
        total_profit_delta = total_payout_delta - total_staked_delta
        
        stats = {
            'total_users': total_users,  # Use the count from leaderboard query
            'total_staked_delta': total_staked_delta,
            'total_payout_delta': total_payout_delta,
            'total_profit_delta': total_profit_delta
        }
        
        # Get backup date for period display
        cursor.execute("""
            SELECT MAX(backup_date) as latest_backup_date 
            FROM User_leader_backup
        """)
        backup_result = cursor.fetchone()
        backup_date = backup_result[0] if backup_result and backup_result[0] else None
        
        # Calculate pagination
        total_pages = (total_users + per_page - 1) // per_page
        
        conn.close()
        
        # Get contest end date
        contest_end_date = get_latest_contest_end_date()
        
        return jsonify({
            'success': True,
            'users': users,
            'stats': stats,
            'backup_date': backup_date,
            'contest_end_date': contest_end_date,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_users,
                'pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user leaderboard: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_leaderboard_bp.route('/api/public/partner-leaderboard')
def get_partner_leaderboard():
    """Get partner leaderboard ranked by betting volume - PUBLIC ACCESS"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM sportsbook_operators")
        total_partners = cursor.fetchone()[0]
        
        # Get partner leaderboard data (only settled bets for volume)
        # Show delta from backup table if available
        cursor.execute("""
            SELECT 
                so.sportsbook_name,
                so.subdomain,
                so.is_active,
                COUNT(DISTINCT u.id) as current_user_count,
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as current_volume,
                COALESCE(pb.user_count, 0) as backup_user_count,
                COALESCE(pb.total_volume, 0) as backup_volume
            FROM sportsbook_operators so
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN bets b ON u.id = b.user_id
            LEFT JOIN (
                SELECT sportsbook_name, user_count, total_volume
                FROM Partner_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM Partner_leader_backup)
            ) pb ON so.sportsbook_name = pb.sportsbook_name
            GROUP BY so.id, so.sportsbook_name, so.subdomain, so.is_active, pb.user_count, pb.total_volume
            ORDER BY current_volume DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        partners = []
        for row in cursor.fetchall():
            # Calculate deltas from backup
            current_user_count = int(row[3])
            current_volume = float(row[4])
            backup_user_count = int(row[5])
            backup_volume = float(row[6])
            
            # Calculate deltas (current - backup)
            user_count_delta = current_user_count - backup_user_count
            volume_delta = current_volume - backup_volume
            
            partners.append({
                'sportsbook_name': row[0],
                'subdomain': row[1],
                'is_active': bool(row[2]),
                'user_count': current_user_count,  # Show absolute user count
                'total_volume': volume_delta,      # Show delta for volume
                'backup_user_count': backup_user_count,
                'backup_volume': backup_volume
            })
        
        # Get total statistics (only settled bets) - calculate deltas
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT so.id) as total_partners,
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as current_total_volume,
                COUNT(DISTINCT u.id) as total_users,
                COALESCE(SUM(pb.total_volume), 0) as backup_total_volume
            FROM sportsbook_operators so
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN bets b ON u.id = b.user_id
            LEFT JOIN (
                SELECT sportsbook_name, total_volume
                FROM Partner_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM Partner_leader_backup)
            ) pb ON so.sportsbook_name = pb.sportsbook_name
        """)
        
        stats_row = cursor.fetchone()
        current_total_volume = float(stats_row[1])
        backup_total_volume = float(stats_row[3])
        
        # Calculate delta
        total_volume_delta = current_total_volume - backup_total_volume
        
        stats = {
            'total_partners': stats_row[0],
            'total_volume_delta': total_volume_delta,
            'total_users': stats_row[2]
        }
        
        # Get backup date for period display
        cursor.execute("""
            SELECT MAX(backup_date) as latest_backup_date 
            FROM Partner_leader_backup
        """)
        backup_result = cursor.fetchone()
        backup_date = backup_result[0] if backup_result and backup_result[0] else None
        
        # Calculate pagination
        total_pages = (total_partners + per_page - 1) // per_page
        
        conn.close()
        
        # Get contest end date
        contest_end_date = get_latest_contest_end_date()
        
        return jsonify({
            'success': True,
            'partners': partners,
            'stats': stats,
            'backup_date': backup_date,
            'contest_end_date': contest_end_date,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_partners,
                'pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting partner leaderboard: {e}")
        return jsonify({'error': 'Internal server error'}), 500

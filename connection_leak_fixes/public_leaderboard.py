"""
Public Leaderboard Routes - No Authentication Required
"""

from flask import Blueprint, jsonify, request
from src import sqlite3_shim as sqlite3
import logging

logger = logging.getLogger(__name__)

public_leaderboard_bp = Blueprint('public_leaderboard', __name__)

def get_db_connection():
    """Get database connection from pool - caller MUST call conn.close()"""
    from src.db_compat import connect
    return connect(use_pool=True)

def get_latest_contest_end_date():
    """Get the latest contest end date from contest_dates table"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
        cursor.execute("""
            SELECT contest_end_date 
            FROM contest_dates 
            WHERE is_active = TRUE 
            ORDER BY contest_end_date DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        
        if result:
            # Return the datetime as ISO format with Z suffix to indicate UTC
            return result[0].isoformat() + 'Z' if hasattr(result[0], 'isoformat') else str(result[0]) + 'Z'
        return None
        
    except Exception as e:
        logger.error(f"Error fetching contest end date: {e}")
        return None
    finally:
        if conn:
            conn.close()

@public_leaderboard_bp.route('/api/public/user-leaderboard')
def get_user_leaderboard():
    """Get user leaderboard ranked by profit - PUBLIC ACCESS"""
    conn = None
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '2000ms'")
        
        # Get total count of profitable users only (profit > 0) - includes casino data
        cursor.execute("""
            SELECT 
                u.id
            FROM users u
            LEFT JOIN (
                SELECT 
                    user_id,
                    SUM(CASE WHEN status IN ('won', 'lost') THEN stake ELSE 0 END) as staked,
                    SUM(CASE WHEN status = 'won' THEN potential_return ELSE 0 END) as payout
                FROM bets
                GROUP BY user_id
            ) sb ON u.id = sb.user_id
            LEFT JOIN (
                SELECT 
                    user_id,
                    SUM(stake) as staked,
                    SUM(payout) as payout
                FROM game_round
                GROUP BY user_id
            ) casino ON u.id::text = casino.user_id
            LEFT JOIN (
                SELECT username, staked, payout, profit
                FROM User_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM User_leader_backup)
            ) ub ON u.username = ub.username
            WHERE ((COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) - 
                   (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0))) - 
                   COALESCE(ub.profit, 0) > 0
        """)
        profitable_users = cursor.fetchall()
        total_users = len(profitable_users)
        
        # Get user leaderboard data with profit calculation (sportsbook + casino)
        # Show delta from backup table if available - ONLY PROFITABLE USERS (profit > 0)
        # Using subqueries to avoid cartesian product from JOIN
        cursor.execute("""
            SELECT 
                u.username,
                u.email,
                -- Sportsbook staked + Casino staked
                (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0)) as current_staked,
                -- Sportsbook payout + Casino payout  
                (COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) as current_payout,
                -- Total profit: (Sportsbook payout + Casino payout) - (Sportsbook staked + Casino staked)
                ((COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) - 
                 (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0))) as current_profit,
                COALESCE(ub.staked, 0) as backup_staked,
                COALESCE(ub.payout, 0) as backup_payout,
                COALESCE(ub.profit, 0) as backup_profit
            FROM users u
            LEFT JOIN (
                SELECT 
                    user_id,
                    SUM(CASE WHEN status IN ('won', 'lost') THEN stake ELSE 0 END) as staked,
                    SUM(CASE WHEN status = 'won' THEN potential_return ELSE 0 END) as payout
                FROM bets
                GROUP BY user_id
            ) sb ON u.id = sb.user_id
            LEFT JOIN (
                SELECT 
                    user_id,
                    SUM(stake) as staked,
                    SUM(payout) as payout
                FROM game_round
                GROUP BY user_id
            ) casino ON u.id::text = casino.user_id
            LEFT JOIN (
                SELECT username, staked, payout, profit
                FROM User_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM User_leader_backup)
            ) ub ON u.username = ub.username
            WHERE ((COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) - 
                   (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0))) - 
                   COALESCE(ub.profit, 0) > 0
            ORDER BY ((COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) - 
                     (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0))) - 
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
        
        # Get total statistics (sportsbook + casino) - calculate deltas - ONLY PROFITABLE USERS
        cursor.execute("""
            SELECT 
                COALESCE(SUM(profitable_users.current_staked), 0) as current_total_staked,
                COALESCE(SUM(profitable_users.current_payout), 0) as current_total_payout,
                COALESCE(SUM(profitable_users.backup_staked), 0) as backup_total_staked,
                COALESCE(SUM(profitable_users.backup_payout), 0) as backup_total_payout
            FROM (
                SELECT 
                    -- Sportsbook staked + Casino staked
                    (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0)) as current_staked,
                    -- Sportsbook payout + Casino payout
                    (COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) as current_payout,
                    COALESCE(ub.staked, 0) as backup_staked,
                    COALESCE(ub.payout, 0) as backup_payout
                FROM users u
                LEFT JOIN (
                    SELECT 
                        user_id,
                        SUM(CASE WHEN status IN ('won', 'lost') THEN stake ELSE 0 END) as staked,
                        SUM(CASE WHEN status = 'won' THEN potential_return ELSE 0 END) as payout
                    FROM bets
                    GROUP BY user_id
                ) sb ON u.id = sb.user_id
                LEFT JOIN (
                    SELECT 
                        user_id,
                        SUM(stake) as staked,
                        SUM(payout) as payout
                    FROM game_round
                    GROUP BY user_id
                ) casino ON u.id::text = casino.user_id
                LEFT JOIN (
                    SELECT username, staked, payout, profit
                    FROM User_leader_backup 
                    WHERE backup_date = (SELECT MAX(backup_date) FROM User_leader_backup)
                ) ub ON u.username = ub.username
                WHERE ((COALESCE(sb.payout, 0) + COALESCE(casino.payout, 0)) - 
                       (COALESCE(sb.staked, 0) + COALESCE(casino.staked, 0))) - 
                       COALESCE(ub.profit, 0) > 0
            ) profitable_users
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
    finally:
        if conn:
            conn.close()

@public_leaderboard_bp.route('/api/public/partner-leaderboard')
def get_partner_leaderboard():
    """Get partner leaderboard ranked by betting volume - PUBLIC ACCESS"""
    conn = None
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '2000ms'")
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM sportsbook_operators")
        total_partners = cursor.fetchone()[0]
        
        # Get partner leaderboard data (sportsbook + casino volume)
        # Show delta from backup table if available
        cursor.execute("""
            SELECT 
                so.sportsbook_name,
                so.subdomain,
                so.is_active,
                COUNT(DISTINCT u.id) as current_user_count,
                -- Sportsbook volume + Casino volume
                (COALESCE(sb_volume.volume, 0) + COALESCE(casino_volume.volume, 0)) as current_volume,
                -- Sportsbook trade count + Casino trade count
                (COALESCE(sb_trades.trade_count, 0) + COALESCE(casino_trades.trade_count, 0)) as current_trade_count,
                COALESCE(pb.user_count, 0) as backup_user_count,
                COALESCE(pb.total_volume, 0) as backup_volume,
                COALESCE(pb.trade_count, 0) as backup_trade_count
            FROM sportsbook_operators so
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN (
                SELECT 
                    u.sportsbook_operator_id,
                    SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END) as volume
                FROM users u
                LEFT JOIN bets b ON u.id = b.user_id
                GROUP BY u.sportsbook_operator_id
            ) sb_volume ON so.id = sb_volume.sportsbook_operator_id
            LEFT JOIN (
                SELECT 
                    u.sportsbook_operator_id,
                    SUM(gr.stake) as volume
                FROM users u
                LEFT JOIN game_round gr ON u.id::text = gr.user_id
                GROUP BY u.sportsbook_operator_id
            ) casino_volume ON so.id = casino_volume.sportsbook_operator_id
            LEFT JOIN (
                SELECT 
                    u.sportsbook_operator_id,
                    SUM(CASE WHEN b.status IN ('won', 'lost') THEN 1 ELSE 0 END) as trade_count
                FROM users u
                LEFT JOIN bets b ON u.id = b.user_id
                GROUP BY u.sportsbook_operator_id
            ) sb_trades ON so.id = sb_trades.sportsbook_operator_id
            LEFT JOIN (
                SELECT 
                    u.sportsbook_operator_id,
                    COUNT(gr.id) as trade_count
                FROM users u
                LEFT JOIN game_round gr ON u.id::text = gr.user_id
                GROUP BY u.sportsbook_operator_id
            ) casino_trades ON so.id = casino_trades.sportsbook_operator_id
            LEFT JOIN (
                SELECT sportsbook_name, user_count, total_volume, trade_count
                FROM Partner_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM Partner_leader_backup)
            ) pb ON so.sportsbook_name = pb.sportsbook_name
            GROUP BY so.id, so.sportsbook_name, so.subdomain, so.is_active, pb.user_count, pb.total_volume, pb.trade_count, sb_volume.volume, casino_volume.volume, sb_trades.trade_count, casino_trades.trade_count
            ORDER BY (COALESCE(sb_volume.volume, 0) + COALESCE(casino_volume.volume, 0)) - COALESCE(pb.total_volume, 0) DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        partners = []
        for row in cursor.fetchall():
            # Calculate deltas from backup
            current_user_count = int(row[3])
            current_volume = float(row[4])
            current_trade_count = int(row[5])
            backup_user_count = int(row[6])
            backup_volume = float(row[7])
            backup_trade_count = int(row[8])
            
            # Calculate deltas (current - backup)
            user_count_delta = current_user_count - backup_user_count
            volume_delta = current_volume - backup_volume
            trade_count_delta = current_trade_count - backup_trade_count
            
            partners.append({
                'sportsbook_name': row[0],
                'subdomain': row[1],
                'is_active': bool(row[2]),
                'user_count': current_user_count,  # Show absolute user count
                'total_volume': volume_delta,      # Show delta for volume
                'trade_count': trade_count_delta,  # Show delta for trade count
                'backup_user_count': backup_user_count,
                'backup_volume': backup_volume,
                'backup_trade_count': backup_trade_count
            })
        
        # Get total statistics (sportsbook + casino volume and trade count) - calculate deltas
        # First get sportsbook total volume and trade count
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as sb_total_volume,
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN 1 ELSE 0 END), 0) as sb_total_trades
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
        """)
        sb_result = cursor.fetchone()
        sb_total_volume = float(sb_result[0])
        sb_total_trades = int(sb_result[1])
        
        # Then get casino total volume and trade count
        cursor.execute("""
            SELECT 
                COALESCE(SUM(gr.stake), 0) as casino_total_volume,
                COALESCE(COUNT(gr.id), 0) as casino_total_trades
            FROM users u
            LEFT JOIN game_round gr ON u.id::text = gr.user_id
        """)
        casino_result = cursor.fetchone()
        casino_total_volume = float(casino_result[0])
        casino_total_trades = int(casino_result[1])
        
        # Finally get partner and user counts and backup data
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT so.id) as total_partners,
                COUNT(DISTINCT u.id) as total_users,
                COALESCE(SUM(pb.total_volume), 0) as backup_total_volume,
                COALESCE(SUM(pb.trade_count), 0) as backup_total_trades
            FROM sportsbook_operators so
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN (
                SELECT sportsbook_name, total_volume, trade_count
                FROM Partner_leader_backup 
                WHERE backup_date = (SELECT MAX(backup_date) FROM Partner_leader_backup)
            ) pb ON so.sportsbook_name = pb.sportsbook_name
        """)
        
        stats_row = cursor.fetchone()
        total_partners = int(stats_row[0])
        total_users = int(stats_row[1])
        backup_total_volume = float(stats_row[2])
        backup_total_trades = int(stats_row[3])
        
        # Calculate combined totals
        current_total_volume = sb_total_volume + casino_total_volume
        current_total_trades = sb_total_trades + casino_total_trades
        
        # Calculate deltas
        total_volume_delta = current_total_volume - backup_total_volume
        total_trade_count_delta = current_total_trades - backup_total_trades
        
        stats = {
            'total_partners': total_partners,
            'total_volume_delta': total_volume_delta,
            'total_trade_count_delta': total_trade_count_delta,
            'total_users': total_users,
            'avg_volume_delta': total_volume_delta / total_partners if total_partners > 0 else 0,
            'avg_trade_count_delta': total_trade_count_delta / total_partners if total_partners > 0 else 0
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
    finally:
        if conn:
            conn.close()

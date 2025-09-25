"""
Casino API integration with sportsbook
Provides casino game endpoints that share authentication and wallet with sportsbook
"""

import json
import asyncio
import time
import os
import sys
from typing import Optional, Dict, Any
from flask import Blueprint, request, jsonify, session
from sqlalchemy import text

# Add src directory to Python path for proper imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from src.config.env_loader import *  # noqa: F401 - just to execute the loader

from src.db_compat import get_connection
import logging

casino_bp = Blueprint('casino', __name__, url_prefix='/api/casino')

# Casino game utilities (simplified versions)
def new_ref(game_type):
    return f"{game_type}_{int(time.time())}_{hash(time.time()) % 10000}"

def spin_reels(target_rtp):
    """Generate 5-reel slot machine result with professional reel strips"""
    import random
    
    # Professional reel strips: 100 stops per reel with exact distribution
    # Using fruit images instead of card numbers
    # 💎: 1, 🍒: 7, 🍌: 7, 🍊: 7, 🍇: 7, 🍓: 19, 🍎: 18, 🥝: 17, 🍑: 17
    reel_strip = []
    
    # Diamond: 1 stop
    reel_strip.extend(['💎'] * 1)
    
    # Fruit symbols: 7 stops each (replacing face cards)
    reel_strip.extend(['🍒'] * 7)  # Cherry (replaces A)
    reel_strip.extend(['🍌'] * 7)  # Banana (replaces K)
    reel_strip.extend(['🍊'] * 7)  # Orange (replaces Q)
    reel_strip.extend(['🍇'] * 7)  # Grape (replaces J)
    
    # More fruit symbols: 19, 18, 17, 17 stops (replacing number cards)
    reel_strip.extend(['🍓'] * 19)  # Strawberry (replaces 10)
    reel_strip.extend(['🍎'] * 18)  # Apple (replaces 9)
    reel_strip.extend(['🥝'] * 17)  # Kiwi (replaces 8)
    reel_strip.extend(['🍑'] * 17)  # Peach (replaces 7)
    
    # Verify we have exactly 100 stops
    assert len(reel_strip) == 100, f"Reel strip should have 100 stops, got {len(reel_strip)}"
    
    # Generate 5 reels with 3 symbols each (3x5 = 15 total symbols)
    reels = []
    for _ in range(5):
        reel = []
        for _ in range(3):
            # Randomly select from the weighted reel strip
            symbol = random.choice(reel_strip)
            reel.append(symbol)
        reels.append(reel)
    
    return reels

def evaluate_slots(reels, stake):
    """Evaluate 5-reel slot machine with professional 20-line paytable (~96.1% RTP)"""
    if not reels or len(reels) != 5:
        return 0, []
    
    print(f"🎰 Evaluating reels: {reels}")
    print(f"🎰 Stake: {stake}")
    
    total_payout = 0
    wins = []
    
    # Professional paytable (multipliers per line bet)
    def get_payout_multiplier(symbol, count):
        """Get payout multiplier based on symbol and count"""
        if count == 5:  # 5 of a kind
            if symbol == '💎':
                return 210.0
            elif symbol in ['🍒', '🍌', '🍊', '🍇']:  # High value fruits
                return 50.0
            else:  # 🍓, 🍎, 🥝, 🍑 (lower value fruits)
                return 25.0
        elif count == 4:  # 4 of a kind
            if symbol == '💎':
                return 20.0
            elif symbol in ['🍒', '🍌', '🍊', '🍇']:  # High value fruits
                return 8.1
            else:  # 🍓, 🍎, 🥝, 🍑 (lower value fruits)
                return 3.35
        elif count == 3:  # 3 of a kind
            if symbol == '💎':
                return 4.0
            elif symbol in ['🍒', '🍌', '🍊', '🍇']:  # High value fruits
                return 1.65
            else:  # 🍓, 🍎, 🥝, 🍑 (lower value fruits)
                return 0.83
        return 0.0
    
    # Check all 20 lines (5 reels x 3 rows = 15 positions, but we check 20 logical lines)
    # For simplicity, we'll check the 3 main horizontal lines and some diagonal patterns
    
    # Line 1: Top row (row 0)
    top_line = [reels[i][0] for i in range(5)]
    line_payout, line_wins = evaluate_line(top_line, stake, get_payout_multiplier, "top")
    total_payout += line_payout
    wins.extend(line_wins)
    
    # Line 2: Middle row (row 1) - main payline
    middle_line = [reels[i][1] for i in range(5)]
    line_payout, line_wins = evaluate_line(middle_line, stake, get_payout_multiplier, "middle")
    total_payout += line_payout
    wins.extend(line_wins)
    
    # Line 3: Bottom row (row 2)
    bottom_line = [reels[i][2] for i in range(5)]
    line_payout, line_wins = evaluate_line(bottom_line, stake, get_payout_multiplier, "bottom")
    total_payout += line_payout
    wins.extend(line_wins)
    
    # Additional lines for 20-line system (simplified - checking more patterns)
    # Lines 4-6: Diagonal patterns
    diag1 = [reels[i][0] if i < 3 else reels[i][2] for i in range(5)]  # Top 3, bottom 2
    line_payout, line_wins = evaluate_line(diag1, stake, get_payout_multiplier, "diag1")
    total_payout += line_payout
    wins.extend(line_wins)
    
    diag2 = [reels[i][2] if i < 3 else reels[i][0] for i in range(5)]  # Bottom 3, top 2
    line_payout, line_wins = evaluate_line(diag2, stake, get_payout_multiplier, "diag2")
    total_payout += line_payout
    wins.extend(line_wins)
    
    # Lines 7-20: Additional patterns (simplified - we'll use the main 3 lines for now)
    # In a full implementation, you'd check all 20 specific line patterns
    
    print(f"🎰 Final result: payout={total_payout}, wins={wins}")
    return total_payout, wins

def evaluate_line(line, stake, get_payout_multiplier, line_name):
    """Evaluate a single line for winning combinations"""
    line_payout = 0
    line_wins = []
    
    print(f"🎰 Evaluating {line_name} line: {line}")
    
    # Check for 5 of a kind (JACKPOT)
    if len(set(line)) == 1:
        symbol = line[0]
        multiplier = get_payout_multiplier(symbol, 5)
        payout = stake * multiplier
        line_payout += payout
        line_wins.append({"symbol": symbol, "count": 5, "payout": payout, "line": line_name})
        print(f"🎰 5 of a kind JACKPOT: {symbol} = {payout} ({multiplier}x)")
    
    # Check for 4 of a kind
    elif len(set(line[:4])) == 1:  # First 4 reels
        symbol = line[0]
        multiplier = get_payout_multiplier(symbol, 4)
        payout = stake * multiplier
        line_payout += payout
        line_wins.append({"symbol": symbol, "count": 4, "payout": payout, "line": line_name})
        print(f"🎰 4 of a kind: {symbol} = {payout} ({multiplier}x)")
    
    # Check for 3 of a kind
    elif len(set(line[:3])) == 1:  # First 3 reels
        symbol = line[0]
        multiplier = get_payout_multiplier(symbol, 3)
        payout = stake * multiplier
        line_payout += payout
        line_wins.append({"symbol": symbol, "count": 3, "payout": payout, "line": line_name})
        print(f"🎰 3 of a kind: {symbol} = {payout} ({multiplier}x)")
    
    # Check for royal sequence (🍒-🍌-🍊-🍇-🍓) - only on main payline
    if line_name == "middle":
        royal_sequence = ['🍒', '🍌', '🍊', '🍇', '🍓']  # Cherry-Banana-Orange-Grape-Strawberry
        if line == royal_sequence:
            multiplier = 100.0  # Royal sequence
            payout = stake * multiplier
            line_payout += payout
            line_wins.append({"symbol": "royal_sequence", "count": 5, "payout": payout, "line": line_name})
            print(f"🎰 Royal sequence: {payout} ({multiplier}x)")
    
    return line_payout, line_wins

def roulette_spin(european=True):
    """Simplified roulette spin"""
    import random
    pocket = random.randint(0, 36 if european else 37)
    color = "red" if pocket in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if pocket != 0 else "green"
    return {"pocket": str(pocket), "color": color}

def fresh_shoe(decks=6):
    """Create fresh blackjack shoe"""
    import random
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = []
    for _ in range(decks):
        for suit in suits:
            for rank in ranks:
                deck.append(f"{rank}{suit}")
    random.shuffle(deck)
    return deck

def bj_value(cards):
    """Calculate blackjack hand value"""
    print(f"🃏 Calculating blackjack value for cards: {cards}")
    value = 0
    aces = 0
    for card in cards:
        rank = card[:-1]  # Remove suit
        print(f"🃏 Card: {card}, Rank: {rank}")
        if rank in ['J', 'Q', 'K']:
            value += 10
            print(f"🃏 Face card: +10, total: {value}")
        elif rank == 'A':
            aces += 1
            value += 11
            print(f"🃏 Ace: +11, total: {value}, aces: {aces}")
        else:
            value += int(rank)
            print(f"🃏 Number card: +{rank}, total: {value}")
    
    print(f"🃏 Before ace adjustment: value={value}, aces={aces}")
    
    # Adjust for aces - convert 11 to 1 if over 21
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
        print(f"🃏 Ace adjustment: value={value}, aces={aces}")
    
    print(f"🃏 Final blackjack value: {value}")
    return value

def baccarat_deal():
    """Simplified baccarat deal"""
    import random
    shoe = fresh_shoe(6)
    player = [shoe.pop(), shoe.pop()]
    banker = [shoe.pop(), shoe.pop()]
    return shoe, player, banker

def baccarat_total(cards):
    """Calculate baccarat total"""
    total = 0
    for card in cards:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            total += 0
        elif rank == 'A':
            total += 1
        else:
            total += int(rank)
    return total % 10

def crash_multiplier(target_rtp):
    """Simplified crash multiplier"""
    import random
    return round(random.uniform(1.0, 10.0), 2)

@casino_bp.route('/health')
def health():
    return jsonify({"ok": True})

@casino_bp.route('/user/info')
def get_user_info():
    """Get current user information from session"""
    try:
        # Enhanced debugging
        print(f"🔍 Casino user/info - Full session: {dict(session)}")
        print(f"🔍 Casino user/info - Session keys: {list(session.keys())}")
        print(f"🔍 Casino user/info - Request headers: {dict(request.headers)}")
        print(f"🔍 Casino user/info - Request URL: {request.url}")
        print(f"🔍 Casino user/info - Request method: {request.method}")
        
        user_id = session.get('user_id')
        print(f"🔍 Casino user/info - user_id from session: {user_id}")
        
        if not user_id:
            print("❌ No user_id found in session")
            return jsonify({
                "error": "Authentication required", 
                "debug": {
                    "session_keys": list(session.keys()),
                    "session_data": dict(session),
                    "headers": dict(request.headers)
                }
            }), 401
        
        operator_id = session.get('operator_id')
        print(f"🔍 Casino user/info - operator_id from session: {operator_id}")
        
        if not operator_id:
            print("❌ No operator_id found in session")
            return jsonify({
                "error": "Sportsbook operator not found",
                "debug": {
                    "session_keys": list(session.keys()),
                    "session_data": dict(session)
                }
            }), 401
        
        # Get user info from database
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, email, balance, created_at, last_login
            FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "User not found"}), 404
        
        username, email, balance, created_at, last_login = result
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "user_id": user_id,
            "operator_id": operator_id,
            "username": username,
            "email": email,
            "balance": balance,
            "created_at": created_at.isoformat() if created_at else None,
            "last_login": last_login.isoformat() if last_login else None
        })
        
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        return jsonify({"error": f"Failed to get user info: {str(e)}"}), 500

@casino_bp.route('/wallet/balance')
def get_balance():
    """Get user's wallet balance from shared sportsbook wallet"""
    try:
        # Debug logging
        print(f"🔍 Casino balance request - Session: {dict(session)}")
        print(f"🔍 Headers: {dict(request.headers)}")
        print(f"🔍 Request URL: {request.url}")
        print(f"🔍 Request method: {request.method}")
        print(f"🔍 Session keys: {list(session.keys())}")
        print(f"🔍 User ID in session: {session.get('user_id')}")
        print(f"🔍 Tenant in session: {session.get('tenant')}")
        
        user_id = session.get('user_id')
        if not user_id:
            # Try to get user_id from request headers as fallback
            user_id = request.headers.get('X-User-Id')
            if not user_id:
                print("❌ No user_id found in session or headers")
                return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            print("❌ No operator_id found in session")
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        print(f"✅ Using user_id: {user_id}, operator_id: {operator_id}")
        
        try:
            conn = get_connection()
            print(f"✅ Database connection successful")
            cursor = conn.cursor()
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return jsonify({"error": f"Database connection failed: {str(e)}"}), 500
        
        # Get balance from user's individual wallet (same as sportsbook)
        try:
            cursor.execute("""
                SELECT balance FROM users 
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (user_id, operator_id))
            
            result = cursor.fetchone()
            balance = result[0] if result else 1000.0  # Default starting balance
            print(f"✅ User balance query successful: {balance}")
            
            cursor.close()
            conn.close()
            
            return jsonify({"balance": round(balance, 2), "currency": "USD"})
        except Exception as e:
            print(f"❌ SQL query failed: {e}")
            cursor.close()
            conn.close()
            return jsonify({"error": f"Database query failed: {str(e)}"}), 500
        
    except Exception as e:
        print(f"❌ Casino balance error: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        logging.error(f"Error getting casino balance: {e}")
        return jsonify({"error": f"Failed to get balance: {str(e)}"}), 500

@casino_bp.route('/slots/spin', methods=['POST'])
def slots_spin():
    """Play slots game"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        
        if stake <= 0:
            return jsonify({"error": "Invalid stake current_balance"}), 400
        
        # Check balance
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current balance
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Debit wallet immediately when placing bet
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (stake, user_id, operator_id))
        
        # Play slots
        ref = new_ref("slots")
        reels = spin_reels(0.96)
        payout, wins = evaluate_slots(reels, stake)
        
        # Store game round
        cursor.execute("""
            INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("slots", user_id, stake, currency, payout, ref, json.dumps({
            "reels": reels,
            "wins": wins
        })))
        
        # Credit winnings only if player won
        if payout > 0:
            cursor.execute("""
                UPDATE users 
                SET balance = balance + %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (payout, user_id, operator_id))
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": payout,
            "result": {
                "reels": reels,
                "wins": wins
            }
        })
        
    except Exception as e:
        logging.error(f"Error in slots spin: {e}")
        return jsonify({"error": "Game error"}), 500

@casino_bp.route('/roulette/spin', methods=['POST'])
def roulette_play():
    """Play roulette game"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        bets = data.get('params', {}).get('bets', [])
        currency = data.get('currency', 'USD')
        
        if not bets:
            return jsonify({"error": "No bets provided"}), 400
        
        total_stake = sum(b.get('current_balance', 0) for b in bets)
        if total_stake <= 0:
            return jsonify({"error": "Invalid stake current_balance"}), 400
        
        # Check balance
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < total_stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Play roulette
        ref = new_ref("roulette")
        spin = roulette_spin(european=True)
        payout = 0.0
        
        for b in bets:
            bet_type = b.get('type')
            current_balance = b.get('current_balance', 0)
            
            if bet_type == "single":
                if str(b.get('value')) == spin["pocket"]:
                    payout += current_balance * 36
            elif bet_type == "color":
                if b.get('value') == spin["color"]:
                    payout += current_balance * 2
            elif bet_type == "even_odd":
                if spin["pocket"] != "0":
                    val = "even" if int(spin["pocket"]) % 2 == 0 else "odd"
                    if b.get('value') == val:
                        payout += current_balance * 2
        
        payout = round(payout, 2)
        
        # Store game round
        cursor.execute("""
            INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("roulette", user_id, total_stake, currency, payout, ref, json.dumps({
            "spin": spin,
            "bets": bets
        })))
        
        # Update wallet
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s + %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (total_stake, payout, user_id, operator_id))
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": total_stake,
            "payout": payout,
            "result": {
                "spin": spin,
                "bets": bets
            }
        })
        
    except Exception as e:
        logging.error(f"Error in roulette play: {e}")
        return jsonify({"error": "Game error"}), 500

@casino_bp.route('/blackjack/play', methods=['POST'])
def blackjack_play():
    """Play blackjack game"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        print(f"🔍 Blackjack request data: {data}")
        print(f"🔍 Request headers: {dict(request.headers)}")
        
        action = data.get('action', 'deal')
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        state = data.get('state', {})
        
        print(f"🔍 Parsed - action: {action}, stake: {stake}, currency: {currency}")
        
        ref = data.get('params', {}).get('ref') or new_ref("blackjack")
        payout = 0.0
        result = {}
        
        conn = get_connection()
        cursor = conn.cursor()
        
        if action == "deal":
            if stake <= 0:
                return jsonify({"error": "Invalid stake current_balance"}), 400
            
            # Check balance
            cursor.execute("""
                SELECT balance FROM users 
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (user_id, operator_id))
            
            result_balance = cursor.fetchone()
            current_balance = result_balance[0] if result_balance else 1000.0
            
            if current_balance < stake:
                return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
            
            # Deal cards
            deck = fresh_shoe(6)
            player = [deck.pop(), deck.pop()]
            dealer = [deck.pop(), deck.pop()]
            pv, dv = bj_value(player), bj_value(dealer)
            
            result = {
                "deck": deck,
                "player": player,
                "dealer": [dealer[0], "🂠"],
                "dealer_real": dealer,
                "pv": pv,
                "dv": dv,
                "ref": ref
            }
            
            if pv == 21:
                payout = round(stake * 2.5, 2)
                result["final"] = True
        else:
            # Hit, stand, double
            deck = state.get('deck', fresh_shoe(6))
            player = state.get('player', [])
            dealer = state.get('dealer_real', [])
            
            if action == "hit":
                player.append(deck.pop())
                pv, dv = bj_value(player), bj_value(dealer)
                result = {
                    "deck": deck,
                    "player": player,
                    "dealer": [dealer[0], "🂠"],
                    "dealer_real": dealer,
                    "pv": pv,
                    "dv": dv,
                    "ref": ref,
                    "final": pv > 21
                }
            else:  # stand or double
                if action == "double":
                    # Check balance for double
                    cursor.execute("""
                        SELECT balance FROM users 
                        WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                    """, (user_id, operator_id))
                    
                    result_balance = cursor.fetchone()
                    current_balance = result_balance[0] if result_balance else 1000.0
                    
                    if current_balance < stake:
                        return jsonify({"error": f"Insufficient funds for double. Available: ${current_balance:.2f}"}), 400
                    
                    player.append(deck.pop())
                    stake *= 2
                
                pv = bj_value(player)
                
                print(f"🃏 Before dealer hits - Dealer cards: {dealer}")
                print(f"🃏 Dealer value before hits: {bj_value(dealer)}")
                
                while bj_value(dealer) < 17:
                    new_card = deck.pop()
                    dealer.append(new_card)
                    print(f"🃏 Dealer hit: {new_card}, new total: {bj_value(dealer)}")
                
                dv = bj_value(dealer)
                
                print(f"🃏 Final blackjack values - Player: {pv}, Dealer: {dv}")
                print(f"🃏 Dealer cards: {dealer}")
                print(f"🃏 Player cards: {player}")
                
                if pv > 21:
                    payout = 0.0
                elif dv > 21 or pv > dv:
                    payout = round(stake * 2, 2)
                elif pv == dv:
                    payout = round(stake, 2)
                else:
                    payout = 0.0
                
                result = {
                    "deck": deck,
                    "player": player,
                    "dealer": dealer,
                    "dealer_real": dealer,
                    "pv": pv,
                    "dv": dv,
                    "ref": ref,
                    "final": True
                }
        
        # Store game round (only for final actions or when there's a payout)
        if action in ["stand", "double"] or payout > 0:
            cursor.execute("""
                INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, ("blackjack", user_id, stake, currency, payout, ref, json.dumps(result)))
        
        # Update wallet - proper flow: debit on bet, credit on win
        if action == "deal":
            # Debit wallet immediately when placing initial bet
            print(f"💰 Blackjack wallet update: debiting stake={stake}")
            cursor.execute("""
                UPDATE users 
                SET balance = balance - %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (stake, user_id, operator_id))
            print(f"💰 Wallet updated: -{stake}")
        elif action == "double":
            # Debit additional stake for double down
            print(f"💰 Blackjack wallet update: debiting additional stake={stake}")
            cursor.execute("""
                UPDATE users 
                SET balance = balance - %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (stake, user_id, operator_id))
            print(f"💰 Wallet updated: -{stake}")
        
        # Credit winnings only if player won (and game is final)
        if payout > 0 and result.get("final"):
            print(f"💰 Blackjack wallet update: crediting winnings={payout}")
            cursor.execute("""
                UPDATE users 
                SET balance = balance + %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (payout, user_id, operator_id))
            print(f"💰 Wallet updated: +{payout}")
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": payout,
            "result": result
        })
        
    except Exception as e:
        logging.error(f"Error in blackjack play: {e}")
        return jsonify({"error": "Game error"}), 500

@casino_bp.route('/baccarat/play', methods=['POST'])
def baccarat_play():
    """Play baccarat game"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        bet_on = data.get('params', {}).get('bet_on', 'player')
        
        if stake <= 0:
            return jsonify({"error": "Invalid stake current_balance"}), 400
        
        # Check balance
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Debit wallet immediately when placing bet
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (stake, user_id, operator_id))
        
        # Play baccarat
        ref = new_ref("baccarat")
        shoe, player, banker = baccarat_deal()
        pt, bt = baccarat_total(player), baccarat_total(banker)
        winner = "player" if pt > bt else ("banker" if bt > pt else "tie")
        
        payout = 0.0
        if winner == "player" and bet_on == "player":
            payout = round(stake * 2, 2)
        elif winner == "banker" and bet_on == "banker":
            payout = round(stake * 1.95, 2)
        elif winner == "tie" and bet_on == "tie":
            payout = round(stake * 9, 2)
        
        # Store game round
        cursor.execute("""
            INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("baccarat", user_id, stake, currency, payout, ref, json.dumps({
            "player": player,
            "banker": banker,
            "player_total": pt,
            "banker_total": bt,
            "winner": winner
        })))
        
        # Credit winnings only if player won
        if payout > 0:
            cursor.execute("""
                UPDATE users 
                SET balance = balance + %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (payout, user_id, operator_id))
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": payout,
            "result": {
                "player": player,
                "banker": banker,
                "player_total": pt,
                "banker_total": bt,
                "winner": winner
            }
        })
        
    except Exception as e:
        logging.error(f"Error in baccarat play: {e}")
        return jsonify({"error": "Game error"}), 500

@casino_bp.route('/crash/play', methods=['POST'])
def crash_play():
    """Play crash game"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        auto_cashout = data.get('params', {}).get('auto_cashout')
        
        if stake <= 0:
            return jsonify({"error": "Invalid stake current_balance"}), 400
        
        # Check balance
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Debit wallet immediately when placing bet
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (stake, user_id, operator_id))
        
        # Play crash - generate crash multiplier but DON'T credit winnings yet
        ref = new_ref("crash")
        multiplier = crash_multiplier(0.96)
        
        # Store game round with 0 payout initially (winnings credited when player actually cashes out)
        cursor.execute("""
            INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("crash", user_id, stake, currency, 0.0, ref, json.dumps({
            "multiplier": multiplier,
            "auto_cashout": auto_cashout,
            "status": "active"  # Game is active, not cashed out yet
        })))
        
        # NO wallet credit here - winnings will be credited when player actually cashes out
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": 0.0,  # No payout until player cashes out
            "result": {
                "multiplier": multiplier,
                "auto_cashout": auto_cashout
            }
        })
        
    except Exception as e:
        logging.error(f"Error in crash play: {e}")
        return jsonify({"error": "Game error"}), 500

@casino_bp.route('/crash/cashout', methods=['POST'])
def crash_cashout():
    """Cash out from crash game"""
    try:
        print(f"🚀 Crash cashout API called")
        user_id = session.get('user_id')
        if not user_id:
            print(f"❌ No user_id in session")
            return jsonify({"error": "Authentication required"}), 401
        
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        ref = data.get('ref')
        cashout_multiplier = data.get('multiplier', 1.0)
        
        print(f"🚀 Cashout data: ref={ref}, multiplier={cashout_multiplier}")
        
        if not ref:
            print(f"❌ No ref provided")
            return jsonify({"error": "Game reference required"}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get the original game round
        cursor.execute("""
            SELECT stake, result_json FROM game_round 
            WHERE ref = %s AND user_id = %s AND game_key = 'crash'
        """, (ref, str(user_id)))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Game not found"}), 404
        
        stake, result_json = result
        
        # Handle both string and dict cases
        if isinstance(result_json, str):
            game_data = json.loads(result_json)
        else:
            game_data = result_json  # Already a dict
            
        crash_multiplier = game_data.get('multiplier', 1.0)
        
        # Calculate payout based on cashout multiplier
        payout = round(stake * cashout_multiplier, 2)
        
        print(f"💰 Calculating payout: stake={stake} * multiplier={cashout_multiplier} = {payout}")
        
        # Update the game round with the actual payout
        updated_game_data = {**game_data, "cashout_multiplier": cashout_multiplier, "status": "cashed_out"}
        cursor.execute("""
            UPDATE game_round 
            SET payout = %s, result_json = %s
            WHERE ref = %s AND user_id = %s
        """, (payout, json.dumps(updated_game_data), ref, str(user_id)))
        
        # Credit winnings to wallet
        cursor.execute("""
            UPDATE users 
            SET balance = balance + %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (payout, user_id, operator_id))
        
        print(f"💰 Wallet credited: +{payout} for user {user_id}")
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": payout,
            "cashout_multiplier": cashout_multiplier,
            "crash_multiplier": crash_multiplier
        })
        
    except Exception as e:
        print(f"❌ Crash cashout error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        logging.error(f"Error in crash cashout: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Cashout error: {str(e)}"}), 500

@casino_bp.route('/history')
def get_game_history():
    """Get user's game history"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        limit = request.args.get('limit', 100, type=int)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get game history from database
        print(f"🔍 Game history - user_id: {user_id} (type: {type(user_id)})")
        print(f"🔍 Game history - operator_id: {operator_id} (type: {type(operator_id)})")
        
        cursor.execute("""
            SELECT id, game_key, user_id, stake, currency, payout, ref, result_json, created_at
            FROM game_round 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT %s
        """, (str(user_id), limit))
        
        rounds = cursor.fetchall()
        print(f"🔍 Game history - Found {len(rounds)} rounds")
        
        history = []
        for round_data in rounds:
            history.append({
                "id": round_data[0],
                "game_key": round_data[1],
                "user_id": round_data[2],
                "stake": float(round_data[3]),
                "currency": round_data[4],
                "payout": float(round_data[5]),
                "ref": round_data[6],
                "result_json": round_data[7] if round_data[7] else {},
                "created_at": round_data[8].isoformat() if round_data[8] else None
            })
        
        conn.close()
        return jsonify({"history": history})
        
    except Exception as e:
        logging.error(f"Error getting game history: {e}")
        return jsonify({"error": "Failed to get history"}), 500

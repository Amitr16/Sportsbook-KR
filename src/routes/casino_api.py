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

def get_tracked_connection():
    """
    DEPRECATED: Get database connection with tracking - casino API version
    WARNING: Callers MUST call conn.close() in a finally block!
    BETTER: Use connection_ctx() context manager instead.
    """
    from src.db_compat import connect
    from src.utils.connection_tracker import track_connection_acquired
    
    # Track this connection acquisition
    context, track_start = track_connection_acquired("casino_api.py::get_tracked_connection")
    conn = connect(use_pool=True, _skip_tracking=True)
    conn._tracking_context = context
    conn._tracking_start = track_start
    return conn

casino_bp = Blueprint('casino', __name__, url_prefix='/api/casino')

# Casino game utilities (simplified versions)
def new_ref(game_type):
    return f"{game_type}_{int(time.time())}_{hash(time.time()) % 10000}"

def spin_reels(target_rtp):
    """Generate 5-reel slot machine result with professional reel strips"""
    import random
    
    # Professional reel strips: 100 stops per reel with exact distribution
    # 🍓: 19%, 🍎: 18%, 🥝: 17%, 🍑: 17%, 🍒/🍌/🍊/🍇: 7% each, 💎: 1%
    reel_strip = []
    
    # Diamond: 1 stop (1%)
    reel_strip.extend(['💎'] * 1)
    
    # High value fruits: 7 stops each (7% each)
    reel_strip.extend(['🍒'] * 7)  # Cherry
    reel_strip.extend(['🍌'] * 7)  # Banana
    reel_strip.extend(['🍊'] * 7)  # Orange
    reel_strip.extend(['🍇'] * 7)  # Grape
    
    # Medium value fruits: 19, 18, 17, 17 stops
    reel_strip.extend(['🍓'] * 19)  # Strawberry (19%)
    reel_strip.extend(['🍎'] * 18)  # Apple (18%)
    reel_strip.extend(['🥝'] * 17)  # Kiwi (17%)
    reel_strip.extend(['🍑'] * 17)  # Peach (17%)
    
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
    """Evaluate 5-reel slot machine with 20 fixed paylines (~96% RTP, ~28% hit rate)"""
    if not reels or len(reels) != 5:
        return 0, []
    
    print(f"🎰 Evaluating reels: {reels}")
    print(f"🎰 Stake: {stake}")
    
    # 20 fixed paylines (row indices per reel)
    LINES = [
        [0,0,0,0,0], [1,1,1,1,1], [2,2,2,2,2], [0,0,0,1,2], [2,2,2,1,0],
        [0,1,2,1,0], [2,1,0,1,2], [0,0,1,2,2], [2,2,1,0,0], [1,0,0,0,1],
        [1,2,2,2,1], [0,1,1,1,0], [2,1,1,1,2], [1,1,0,1,1], [1,1,2,1,1],
        [0,1,0,1,0], [2,1,2,1,2], [0,2,0,2,0], [2,0,2,0,2], [0,2,1,0,2]
    ]
    
    # Paytable (multipliers per line bet) - 94% RTP
    # Nice-number paytable that yields ~94% RTP
    PAYTABLE = {
        'diamond': {3: 81.0, 4: 400.0, 5: 4200.0},
        'high': {3: 33.0, 4: 160.0, 5: 1005.0},      # 🍒🍌🍊🍇
        'medium': {3: 17.0, 4: 66.0, 5: 505.0}    # 🍓🍎🥝🍑
    }
    
    ROYAL_PAYOUT = 2000.0  # Royal sequence on line 2 (middle row)
    ROYAL_SEQUENCE = ['🍒', '🍌', '🍊', '🍇', '🍓']
    
    def get_symbol_bucket(symbol):
        """Get symbol bucket for paytable lookup"""
        if symbol == '💎':
            return 'diamond'
        elif symbol in ['🍒', '🍌', '🍊', '🍇']:
            return 'high'
        else:  # 🍓, 🍎, 🥝, 🍑
            return 'medium'
    
    def longest_prefix_match(seq):
        """Find longest prefix of identical symbols"""
        if not seq:
            return 0
        k = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[0]:
                k += 1
            else:
                break
        return k
    
    total_payout = 0.0
    wins = []
    line_bet = stake / 20.0  # Total stake divided by 20 lines
    
    # Evaluate each payline
    for line_idx, line in enumerate(LINES):
        # Extract symbols along this payline
        seq = [reels[reel][line[reel]] for reel in range(5)]
        
        # Check for Royal sequence first (highest priority) - only on line 2 (middle row)
        if line_idx == 1 and seq == ROYAL_SEQUENCE:
            # Royal sequence on middle row (line 2, 1-indexed)
            payout = line_bet * ROYAL_PAYOUT
            total_payout += payout
            
            wins.append({
                "symbol": "royal_sequence",
                "count": 5,
                "payout": payout,
                "line": "line_2_royal",
                "multiplier": ROYAL_PAYOUT
            })
            print(f"🎰 Line {line_idx+1}: Royal Sequence = {payout:.2f} ({ROYAL_PAYOUT}x)")
        else:
            # Check for longest prefix match (3+ symbols) for all other cases
            k = longest_prefix_match(seq)
            
            if k >= 3:
                # Regular win: k-of-a-kind
                symbol = seq[0]
                bucket = get_symbol_bucket(symbol)
                multiplier = PAYTABLE[bucket][k]
                payout = line_bet * multiplier
                total_payout += payout
                
                wins.append({
                    "symbol": symbol,
                    "count": k,
                    "payout": payout,
                    "line": f"line_{line_idx+1}",
                    "multiplier": multiplier
                })
                print(f"🎰 Line {line_idx+1}: {symbol} {k} of a kind = {payout:.2f} ({multiplier}x)")
    
    print(f"🎰 Final result: payout={total_payout:.2f}, wins={len(wins)}")
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
            multiplier = 2000.0  # Royal sequence: 2000x
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
        # Handle both string format ('7S') and dict format ({'r': '7', 's': 'spades'})
        if isinstance(card, dict):
            rank = card.get('r', card.get('rank', ''))
        else:
            rank = card[:-1]  # Remove suit from string format
        print(f"🃏 Card: {card}, Rank: {rank}")
        
        if rank in ['J', 'Q', 'K']:
            value += 10
            print(f"🃏 Face card: +10, total: {value}")
        elif rank == 'A':
            aces += 1
            value += 11
            print(f"🃏 Ace: +11, total: {value}, aces: {aces}")
        else:
            try:
                value += int(rank)
                print(f"🃏 Number card: +{rank}, total: {value}")
            except ValueError:
                print(f"🃏 Invalid rank: {rank}")
    
    print(f"🃏 Before ace adjustment: value={value}, aces={aces}")
    
    # Adjust for aces - convert 11 to 1 if over 21
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
        print(f"🃏 Ace adjustment: value={value}, aces={aces}")
    
    print(f"🃏 Final blackjack value: {value}")
    return value

def settle_split_hands(split_hands, dealer, deck, stake, ref):
    """Settle all split hands against dealer"""
    # Play dealer hand
    while bj_value(dealer) < 17:
        dealer.append(deck.pop())
    
    dealer_value = bj_value(dealer)
    total_payout = 0.0
    results = []
    
    print(f"🃏 SPLIT SETTLEMENT - Dealer value: {dealer_value}")
    
    for i, hand in enumerate(split_hands):
        hand_cards = hand['cards']
        hand_value = bj_value(hand_cards)
        
        print(f"🃏 Split Hand {i+1}: {hand_cards} = {hand_value}")
        
        if hand_value > 21:
            # Hand busted
            hand_payout = 0.0
            result_type = "bust"
        elif dealer_value > 21:
            # Dealer busted
            hand_payout = stake * 2
            result_type = "win"
        elif hand_value > dealer_value:
            # Player wins
            hand_payout = stake * 2
            result_type = "win"
        elif hand_value == dealer_value:
            # Push
            hand_payout = stake
            result_type = "push"
        else:
            # Player loses
            hand_payout = 0.0
            result_type = "lose"
        
        total_payout += hand_payout
        results.append({
            "hand": i + 1,
            "cards": hand_cards,
            "value": hand_value,
            "payout": hand_payout,
            "result": result_type
        })
        
        print(f"🃏 Split Hand {i+1} result: {result_type}, payout: {hand_payout}")
    
    # Credit total winnings
    if total_payout > 0:
        temp_conn = None
        try:
            temp_conn = get_tracked_connection()
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("""
                UPDATE users 
                SET balance = balance + %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (total_payout, session.get('user_id'), session.get('operator_id')))
            temp_conn.commit()
            temp_cursor.close()
            print(f"💰 Split hands total payout credited: +{total_payout}")
        finally:
            if temp_conn:
                temp_conn.close()
    
    return {
        "deck": deck,
        "player": [],
        "split_hands": split_hands,
        "current_hand": len(split_hands),  # All hands played
        "dealer": dealer,
        "dealer_real": dealer,
        "pv": 0,  # No current hand
        "dv": dealer_value,
        "ref": ref,
        "final": True,
        "total_payout": total_payout,
        "results": results
    }

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

def hmac_sha256(key, msg):
    """HMAC-SHA256 implementation"""
    import hmac
    import hashlib
    return hmac.new(key.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()

def hash_to_uniform_01(hex_string):
    """Convert first 52 bits of hex string to float in [0,1)"""
    # First 52 bits → 13 hex chars (13 * 4 = 52)
    frac_hex = hex_string[:13]
    h = int(frac_hex, 16)
    E = 2 ** 52
    return h / E  # r in [0, 1)

def uniform_from_seeds(server_seed, client_seed, nonce):
    """Generate provably fair uniform random number from seeds"""
    msg = f"{client_seed}:{nonce}"
    hex_hash = hmac_sha256(server_seed, msg)
    return hash_to_uniform_01(hex_hash)

def crash_multiplier(target_rtp, server_seed="default_server_seed", client_seed="default_client_seed", nonce=0):
    """Provably fair crash multiplier with exact RTP = target_rtp"""
    alpha = float(target_rtp)  # e.g. 0.96

    # provably-fair r in [0,1)
    r = uniform_from_seeds(server_seed, client_seed, nonce)

    # ✅ Correct α-scaled fair crash:
    #   M_fair = 1/(1-r) has tail P(M_fair >= x) = 1/x
    #   M = α * M_fair  ⇒  P(M >= x) = α/x  ⇒ EV at any cashout x is α
    denom = max(1e-12, 1.0 - r)
    m = alpha / denom

    # Map the <1x mass (prob = 1-α) to an explicit 1.00x insta-bust
    if m < 1.0:
        m = 1.0

    # Cap at 20x for risk management (matches UI)
    m = min(m, 20.0)

    return round(m, 2)

@casino_bp.route('/health')
def health():
    return jsonify({"ok": True})

@casino_bp.route('/user/info')
def get_user_info():
    """Get current user information from session"""
    conn = None
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
        conn = None
        try:
            conn = get_tracked_connection()
            cursor = conn.cursor()
            cursor.execute("SET LOCAL statement_timeout = '1500ms'")
            
            cursor.execute("""
                SELECT username, email, balance, created_at, last_login, is_active
                FROM users 
                WHERE id = %s AND sportsbook_operator_id = %s
            """, (user_id, operator_id))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({"error": "User not found"}), 404
            
            username, email, balance, created_at, last_login, is_active = result
            
            # Check if user is disabled
            if not is_active:
                return jsonify({"error": "Account has been disabled by administrator", "is_active": False}), 403
            
            cursor.close()
            conn.close()
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
        
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
    finally:
        if conn:
            conn.close()

@casino_bp.route('/wallet/balance')
def get_balance():
    """Get user's wallet balance from shared sportsbook wallet"""
    conn = None
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
        
        conn = None
        try:
            conn = get_tracked_connection()
            print(f"✅ Database connection successful")
            cursor = conn.cursor()
            cursor.execute("SET LOCAL statement_timeout = '1500ms'")
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
    finally:
        if conn:
            conn.close()

@casino_bp.route('/slots/bet', methods=['POST'])
def slots_bet():
    """Place a slots bet - debits stake only"""
    conn = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        
        if stake <= 0:
            return jsonify({"error": "Invalid stake amount"}), 400
        
        # Check balance
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Debit wallet immediately
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (stake, user_id, operator_id))
        
        conn.commit()
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user_id, stake, "Slots bet")
        except Exception as web3_error:
            logging.warning(f"Web3 sync failed for slots bet: {web3_error}")
        
        # Generate ref for this bet
        ref = new_ref("slots")
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "status": "bet_placed"
        })
        
    except Exception as e:
        logging.error(f"Error in slots bet: {e}")
        return jsonify({"error": "Bet error"}), 500
    finally:
        if conn:
            conn.close()

@casino_bp.route('/slots/result', methods=['POST'])
def slots_result():
    """Process slots result - credits winnings"""
    conn = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        ref = data.get('ref')
        stake = data.get('stake', 0)
        currency = data.get('currency', 'USD')
        
        if not ref or stake <= 0:
            return jsonify({"error": "Invalid request"}), 400
        
        # Play slots
        reels = spin_reels(0.96)
        payout, wins = evaluate_slots(reels, stake)
        
        # Store game round
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
        
        # Sync Web3 wallet credit (non-blocking) if player won
        if payout > 0:
            try:
                from src.services.web3_sync_service import sync_web3_credit
                sync_web3_credit(user_id, payout, "Slots win")
            except Exception as web3_error:
                logging.warning(f"Web3 sync failed for slots win: {web3_error}")
        
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
        logging.error(f"Error in slots result: {e}")
        return jsonify({"error": "Result error"}), 500
    finally:
        if conn:
            conn.close()

@casino_bp.route('/roulette/spin', methods=['POST'])
def roulette_play():
    """Play roulette game"""
    conn = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        print(f"🎰 Roulette request data: {data}")
        bets = data.get('params', {}).get('bets', [])
        currency = data.get('currency', 'USD')
        
        print(f"🎰 Roulette bets: {bets}")
        
        if not bets:
            print(f"❌ No bets provided")
            return jsonify({"error": "No bets provided"}), 400
        
        total_stake = sum(b.get('stake', b.get('amount', 0)) for b in bets)
        if total_stake <= 0:
            return jsonify({"error": "Invalid stake amount"}), 400
        
        # Check balance
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
        cursor.execute("""
            SELECT balance FROM users 
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (user_id, operator_id))
        
        result = cursor.fetchone()
        current_balance = result[0] if result else 1000.0
        
        if current_balance < total_stake:
            return jsonify({"error": f"Insufficient funds. Available: ${current_balance:.2f}"}), 400
        
        # Debit wallet immediately when placing bet
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s
            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
        """, (total_stake, user_id, operator_id))
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user_id, total_stake, "Roulette bet")
        except Exception as web3_error:
            logging.warning(f"Web3 sync failed for roulette bet: {web3_error}")
        
        # Play roulette
        ref = new_ref("roulette")
        spin = roulette_spin(european=True)
        payout = 0.0
        
        print(f"🎰 DEBUG: Checking {len(bets)} bets against winning number {spin['pocket']} (color: {spin['color']})")
        
        for b in bets:
            bet_type = b.get('type')
            stake = b.get('stake', b.get('amount', 0))
            bet_value = b.get('value')
            
            print(f"🎰 DEBUG: Bet - type: {bet_type}, value: {bet_value}, stake: {stake}")
            
            # Normalize bet types from frontend
            if bet_type == "straight":
                bet_type = "single"
            elif bet_type in ["even", "odd"]:
                bet_type = "even_odd"
            elif bet_type == "range":
                bet_type = "low_high"
            
            if bet_type == "single":
                print(f"🎰 DEBUG: Single bet check - bet value: {bet_value} (type: {type(bet_value)}), spin: {spin['pocket']} (type: {type(spin['pocket'])})")
                print(f"🎰 DEBUG: Comparison - str(bet_value)='{str(bet_value)}' == str(spin['pocket'])='{str(spin['pocket'])}'? {str(bet_value) == str(spin['pocket'])}")
                if str(bet_value) == str(spin["pocket"]):
                    payout += stake * 36
                    print(f"🎰 DEBUG: ✅ WIN! Single number match: +{stake * 36}")
            elif bet_type == "color":
                if bet_value == spin["color"]:
                    payout += stake * 2
                    print(f"🎰 DEBUG: ✅ WIN! Color match: +{stake * 2}")
            elif bet_type == "even_odd":
                if spin["pocket"] != "0":
                    val = "even" if int(spin["pocket"]) % 2 == 0 else "odd"
                    if bet_value == val:
                        payout += stake * 2
                        print(f"🎰 DEBUG: ✅ WIN! Even/Odd match: +{stake * 2}")
            elif bet_type == "low_high":
                if spin["pocket"] != "0":
                    val = "low" if int(spin["pocket"]) <= 18 else "high"
                    if bet_value == val:
                        payout += stake * 2
                        print(f"🎰 DEBUG: ✅ WIN! Low/High match: +{stake * 2}")
            elif bet_type == "dozen":
                # Handle dozen bets (1st12, 2nd12, 3rd12)
                if spin["pocket"] != "0":
                    num = int(spin["pocket"])
                    if bet_value == '1st12' and 1 <= num <= 12:
                        payout += stake * 3
                        print(f"🎰 DEBUG: ✅ WIN! Dozen match: +{stake * 3}")
                    elif bet_value == '2nd12' and 13 <= num <= 24:
                        payout += stake * 3
                        print(f"🎰 DEBUG: ✅ WIN! Dozen match: +{stake * 3}")
                    elif bet_value == '3rd12' and 25 <= num <= 36:
                        payout += stake * 3
                        print(f"🎰 DEBUG: ✅ WIN! Dozen match: +{stake * 3}")
        
        print(f"🎰 DEBUG: Total calculated payout: ${payout}")
        
        payout = round(payout, 2)
        
        # Store game round with calculated payout (but don't credit yet - frontend calls /roulette/win to credit)
        cursor.execute("""
            INSERT INTO game_round (game_key, user_id, stake, currency, payout, ref, result_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("roulette", user_id, total_stake, currency, payout, ref, json.dumps({
            "spin": spin,
            "bets": bets,
            "status": "active"  # Will be completed when /roulette/win is called
        })))
        
        conn.commit()
        
        return jsonify({
            "ref": ref,
            "stake": total_stake,
            "payout": payout,  # Return calculated payout for frontend to display
            "result": {
                "spin": spin,
                "bets": bets
            }
        })
        
    except Exception as e:
        logging.error(f"Error in roulette play: {e}")
        return jsonify({"error": "Game error"}), 500
    finally:
        if conn:
            conn.close()

@casino_bp.route('/roulette/win', methods=['POST'])
def roulette_win():
    """Credit winnings for roulette game"""
    conn = None
    try:
        print(f"🎰 Roulette win API called")
        user_id = session.get('user_id')
        if not user_id:
            print(f"❌ No user_id in session")
            return jsonify({"error": "Authentication required"}), 401
        
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        data = request.get_json()
        ref = data.get('ref')
        payout = data.get('payout', 0.0)
        
        print(f"🎰 Roulette win data: ref={ref}, payout={payout}")
        
        if not ref:
            print(f"❌ No ref provided")
            return jsonify({"error": "Game reference required"}), 400
        
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
        # Get the original game round
        cursor.execute("""
            SELECT stake, result_json FROM game_round 
            WHERE ref = %s AND user_id = %s AND game_key = 'roulette'
        """, (ref, str(user_id)))
        
        result = cursor.fetchone()
        if not result:
            print(f"❌ Game not found for ref: {ref}")
            return jsonify({"error": "Game not found"}), 404
        
        stake, result_json = result
        
        # Handle both string and dict cases
        if isinstance(result_json, str):
            game_data = json.loads(result_json)
        else:
            game_data = result_json  # Already a dict
        
        # Update the game round with the actual payout
        updated_game_data = {**game_data, "payout": payout, "status": "completed"}
        cursor.execute("""
            UPDATE game_round 
            SET payout = %s, result_json = %s
            WHERE ref = %s AND user_id = %s
        """, (payout, json.dumps(updated_game_data), ref, str(user_id)))
        
        # Credit winnings to wallet
        if payout > 0:
            cursor.execute("""
                UPDATE users 
                SET balance = balance + %s
                WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
            """, (payout, user_id, operator_id))
            print(f"💰 Roulette winnings credited: +{payout} for user {user_id}")
        
        conn.commit()
        
        # Sync Web3 wallet credit (non-blocking) if player won
        if payout > 0:
            try:
                from src.services.web3_sync_service import sync_web3_credit
                sync_web3_credit(user_id, payout, "Roulette win")
            except Exception as web3_error:
                logging.warning(f"Web3 sync failed for roulette win: {web3_error}")
        
        return jsonify({
            "ref": ref,
            "stake": stake,
            "payout": payout
        })
        
    except Exception as e:
        print(f"❌ Roulette win error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        logging.error(f"Error in roulette win: {e}")
        return jsonify({"error": f"Win error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@casino_bp.route('/blackjack/play', methods=['POST'])
def blackjack_play():
    """Play blackjack game"""
    from src.db_compat import connection_ctx
    
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
        additional_stake_for_double = 0  # Track additional stake for double (used in wallet update)
        
        with connection_ctx(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
                
                # Use frontend's game state if provided, otherwise generate new cards
                if data.get("state") and data["state"].get("deck") and data["state"].get("player") and data["state"].get("dealer_real"):
                    # Use frontend's cards
                    deck = data["state"]["deck"]
                    player = data["state"]["player"]
                    dealer = data["state"]["dealer_real"]
                    print(f"🃏 DEBUG: Using frontend cards - player: {player}, dealer: {dealer}")
                else:
                    # Fallback: generate new cards
                    deck = fresh_shoe(6)
                    player = [deck.pop(), deck.pop()]
                    dealer = [deck.pop(), deck.pop()]
                    print(f"🃏 DEBUG: Generated new cards - player: {player}, dealer: {dealer}")
                
                pv, dv = bj_value(player), bj_value(dealer)
                print(f"🃏 DEBUG: Player value: {pv}, Dealer value: {dv}")
                
                result = {
                    "deck": deck,
                    "player": player,
                    "dealer": [dealer[0], "🂠"],
                    "dealer_real": dealer,
                    "pv": pv,
                    "dv": dv,
                    "ref": ref
                }
                
                # Check for blackjack on deal
                if pv == 21:
                    # Check if dealer also has blackjack
                    if dv == 21:
                        outcome = "Push"
                        multiplier = "+0x"
                        payout = round(stake, 2)
                        result["final"] = True
                        print(f"💰 BOTH BLACKJACK! Push - returning stake: {payout}")
                    else:
                        outcome = "Blackjack"
                        multiplier = "+1.5x"
                        payout = round(stake * 2.5, 2)
                        result["final"] = True
                        # Credit Blackjack winnings immediately
                        print(f"💰 PLAYER BLACKJACK! Crediting winnings={payout}")
                        cursor.execute("""
                            UPDATE users 
                            SET balance = balance + %s
                            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                        """, (payout, user_id, operator_id))
                        print(f"💰 Blackjack wallet updated: +{payout}")
                    
                    result["outcome"] = outcome
                    result["multiplier"] = multiplier
                    result["payout"] = payout
                else:
                    print(f"💰 No Blackjack. Player value: {pv}, Payout: 0")
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
                elif action == "split":
                    # Handle split action
                    print(f"🃏 SPLIT ACTION - Player cards: {player}")
                    
                    # Check if we can split (same rank cards)
                    if len(player) != 2 or player[0]['r'] != player[1]['r']:
                        return jsonify({"error": "Cannot split - cards must be same rank"}), 400
                    
                    # Check balance for additional bet
                    cursor.execute("""
                        SELECT balance FROM users 
                        WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                    """, (user_id, operator_id))
                    
                    result_balance = cursor.fetchone()
                    current_balance = result_balance[0] if result_balance else 1000.0
                    
                    if current_balance < stake:
                        return jsonify({"error": f"Insufficient funds for split. Need additional ${stake:.2f}"}), 400
                    
                    # Debit additional stake for split
                    cursor.execute("""
                        UPDATE users 
                        SET balance = balance - %s
                        WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                    """, (stake, user_id, operator_id))
                    print(f"💰 Split additional bet debited: -{stake}")
                    
                    # Create split hands
                    card1, card2 = player[0], player[1]
                    split_hand1 = [card1, deck.pop()]
                    split_hand2 = [card2, deck.pop()]
                    
                    # Calculate values for both hands
                    pv1, pv2 = bj_value(split_hand1), bj_value(split_hand2)
                    dv = bj_value(dealer)
                    
                    result = {
                        "deck": deck,
                        "player": [],  # Clear original player hand
                        "split_hands": [
                            {"cards": split_hand1, "value": pv1},
                            {"cards": split_hand2, "value": pv2}
                        ],
                        "current_hand": 0,  # Start with first split hand
                        "dealer": [dealer[0], "🂠"],
                        "dealer_real": dealer,
                        "pv": pv1,  # Current hand value
                        "dv": dv,
                        "ref": ref,
                        "can_split_hand1": split_hand1[0]['r'] == split_hand1[1]['r'] if len(split_hand1) == 2 else False,
                        "can_split_hand2": split_hand2[0]['r'] == split_hand2[1]['r'] if len(split_hand2) == 2 else False
                    }
                    
                    print(f"🃏 SPLIT RESULT - Hand 1: {split_hand1} (value: {pv1}), Hand 2: {split_hand2} (value: {pv2})")
                elif action in ["hit_split", "stand_split", "double_split"]:
                    # Handle split hand actions
                    split_hands = state.get('split_hands', [])
                    current_hand = state.get('current_hand', 0)
                    
                    if not split_hands or current_hand >= len(split_hands):
                        return jsonify({"error": "Invalid split hand"}), 400
                    
                    current_split_hand = split_hands[current_hand]
                    current_cards = current_split_hand.get('cards', [])
                    
                    if action == "hit_split":
                        current_cards.append(deck.pop())
                        current_split_hand['cards'] = current_cards
                        current_split_hand['value'] = bj_value(current_cards)
                        split_hands[current_hand] = current_split_hand
                        
                        result = {
                            "deck": deck,
                            "player": [],
                            "split_hands": split_hands,
                            "current_hand": current_hand,
                            "dealer": [dealer[0], "🂠"],
                            "dealer_real": dealer,
                            "pv": bj_value(current_cards),
                            "dv": bj_value(dealer),
                            "ref": ref,
                            "final": bj_value(current_cards) > 21
                        }
                    elif action == "double_split":
                        # Check balance for double on split hand
                        cursor.execute("""
                            SELECT balance FROM users 
                            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                        """, (user_id, operator_id))
                        
                        result_balance = cursor.fetchone()
                        current_balance = result_balance[0] if result_balance else 1000.0
                        
                        if current_balance < stake:
                            return jsonify({"error": f"Insufficient funds for double on split hand"}), 400
                        
                        # Debit additional stake for double
                        cursor.execute("""
                            UPDATE users 
                            SET balance = balance - %s
                            WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                        """, (stake, user_id, operator_id))
                        print(f"💰 Split hand double bet debited: -{stake}")
                        
                        current_cards.append(deck.pop())
                        current_split_hand['cards'] = current_cards
                        current_split_hand['value'] = bj_value(current_cards)
                        split_hands[current_hand] = current_split_hand
                        
                        # Move to next split hand or settle
                        current_hand += 1
                        if current_hand >= len(split_hands):
                            # All split hands played, settle all hands
                            result = settle_split_hands(split_hands, dealer, deck, stake, ref)
                        else:
                            result = {
                                "deck": deck,
                                "player": [],
                                "split_hands": split_hands,
                                "current_hand": current_hand,
                                "dealer": [dealer[0], "🂠"],
                                "dealer_real": dealer,
                                "pv": bj_value(split_hands[current_hand]['cards']),
                                "dv": bj_value(dealer),
                                "ref": ref,
                                "final": False
                            }
                    else:  # stand_split
                        # Move to next split hand or settle
                        current_hand += 1
                        if current_hand >= len(split_hands):
                            # All split hands played, settle all hands
                            result = settle_split_hands(split_hands, dealer, deck, stake, ref)
                        else:
                            result = {
                                "deck": deck,
                                "player": [],
                                "split_hands": split_hands,
                                "current_hand": current_hand,
                                "dealer": [dealer[0], "🂠"],
                                "dealer_real": dealer,
                                "pv": bj_value(split_hands[current_hand]['cards']),
                                "dv": bj_value(dealer),
                                "ref": ref,
                                "final": False
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
                        
                        # Save the additional stake needed before doubling (original stake amount)
                        additional_stake_for_double = stake
                        print(f"🃏 DEBUG: Double - Original stake: ${stake}, Additional stake to debit: ${additional_stake_for_double}")
                        
                        if current_balance < additional_stake_for_double:
                            return jsonify({"error": f"Insufficient funds for double. Available: ${current_balance:.2f}"}), 400
                        
                        player.append(deck.pop())
                        stake *= 2  # Double the stake for payout calculation only
                        print(f"🃏 DEBUG: Double - Stake doubled for payout calc: ${stake}, But will debit: ${additional_stake_for_double}")
                    
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
                    
                    # Determine outcome and payout
                    if pv > 21:
                        outcome = "Bust"
                        multiplier = "-1x"
                        payout = 0.0
                    elif dv > 21:
                        outcome = "Win"
                        multiplier = "+1x"
                        payout = round(stake * 2, 2)
                    elif pv > dv:
                        # Check for blackjack (21 with exactly 2 cards)
                        if pv == 21 and len(player) == 2:
                            outcome = "Blackjack"
                            multiplier = "+1.5x"
                            payout = round(stake * 2.5, 2)
                        else:
                            outcome = "Win"
                            multiplier = "+1x"
                            payout = round(stake * 2, 2)
                    elif pv == dv:
                        outcome = "Push"
                        multiplier = "+0x"
                        payout = round(stake, 2)
                    else:
                        outcome = "Lose"
                        multiplier = "-1x"
                        payout = 0.0
                    
                    print(f"🃏 Game result - Outcome: {outcome}, Multiplier: {multiplier}, Payout: {payout}")
                    
                    result = {
                        "deck": deck,
                        "player": player,
                        "dealer": dealer,
                        "dealer_real": dealer,
                        "pv": pv,
                        "dv": dv,
                        "outcome": outcome,
                        "multiplier": multiplier,
                        "payout": payout,
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
                
                # Sync Web3 wallet debit (non-blocking)
                try:
                    from src.services.web3_sync_service import sync_web3_debit
                    sync_web3_debit(user_id, stake, "Blackjack bet")
                except Exception as web3_error:
                    logging.warning(f"Web3 sync failed for blackjack bet: {web3_error}")
                    
            elif action == "double":
                # Debit additional stake for double down (original stake amount, not doubled)
                print(f"💰 DEBUG: Double wallet debit - additional_stake_for_double={additional_stake_for_double}, stake={stake}")
                if additional_stake_for_double == 0:
                    print(f"⚠️ WARNING: additional_stake_for_double is 0! This should not happen. Using stake/2 instead.")
                    additional_stake_for_double = stake / 2
                print(f"💰 Blackjack wallet update: debiting additional stake={additional_stake_for_double}")
                cursor.execute("""
                    UPDATE users 
                    SET balance = balance - %s
                    WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                """, (additional_stake_for_double, user_id, operator_id))
                print(f"💰 Wallet updated: -{additional_stake_for_double}")
                
                # Sync Web3 wallet debit for double down (non-blocking)
                try:
                    from src.services.web3_sync_service import sync_web3_debit
                    sync_web3_debit(user_id, additional_stake_for_double, "Blackjack double down")
                except Exception as web3_error:
                    logging.warning(f"Web3 sync failed for blackjack double down: {web3_error}")
            
            # Credit winnings only if player won (and game is final)
            if payout > 0 and result.get("final"):
                print(f"💰 Blackjack wallet update: crediting winnings={payout}")
                cursor.execute("""
                    UPDATE users 
                    SET balance = balance + %s
                    WHERE id = %s AND sportsbook_operator_id = %s AND is_active = true
                """, (payout, user_id, operator_id))
                print(f"💰 Wallet updated: +{payout}")
                
                # Sync Web3 wallet credit (non-blocking)
                try:
                    from src.services.web3_sync_service import sync_web3_credit
                    sync_web3_credit(user_id, payout, "Blackjack win")
                except Exception as web3_error:
                    logging.warning(f"Web3 sync failed for blackjack win: {web3_error}")
            else:
                print(f"💰 Blackjack wallet update: no payout to credit (payout={payout}, final={result.get('final')})")
            
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
    conn = None
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
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user_id, stake, "Baccarat bet")
        except Exception as web3_error:
            logging.warning(f"Web3 sync failed for baccarat bet: {web3_error}")
        
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
            
            # Sync Web3 wallet credit (non-blocking) if player won
            try:
                from src.services.web3_sync_service import sync_web3_credit
                sync_web3_credit(user_id, payout, "Baccarat win")
            except Exception as web3_error:
                logging.warning(f"Web3 sync failed for baccarat win: {web3_error}")
        
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
    finally:
        if conn:
            conn.close()

@casino_bp.route('/crash/play', methods=['POST'])
def crash_play():
    """Play crash game"""
    conn = None
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
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user_id, stake, "Crash bet")
        except Exception as web3_error:
            logging.warning(f"Web3 sync failed for crash bet: {web3_error}")
        
        # Play crash - generate crash multiplier but DON'T credit winnings yet
        ref = new_ref("crash")
        
        # Generate provably fair seeds
        import time
        server_seed = f"server_{int(time.time())}"
        client_seed = f"client_{user_id}_{int(time.time())}"
        nonce = int(time.time() * 1000) % 1000000  # Use timestamp as nonce
        
        multiplier = crash_multiplier(0.96, server_seed, client_seed, nonce)
        
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
    finally:
        if conn:
            conn.close()

@casino_bp.route('/crash/cashout', methods=['POST'])
def crash_cashout():
    """Cash out from crash game"""
    conn = None
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
        
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
        
        # Enforce server-side cashout validity - prevent claiming after crash
        crash_multiplier_value = float(crash_multiplier)
        if float(cashout_multiplier) > crash_multiplier_value:
            return jsonify({"error": "Cashout after crash is invalid"}), 400
        
        # Calculate payout based on cashout multiplier (convert to float to avoid decimal/float multiplication error)
        payout = round(float(stake) * float(cashout_multiplier), 2)
        
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
        
        # Sync Web3 wallet credit (non-blocking) if player won
        try:
            from src.services.web3_sync_service import sync_web3_credit
            sync_web3_credit(user_id, payout, "Crash cashout win")
        except Exception as web3_error:
            logging.warning(f"Web3 sync failed for crash cashout: {web3_error}")
        
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
    finally:
        if conn:
            conn.close()

@casino_bp.route('/history')
def get_game_history():
    """Get user's game history"""
    conn = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get the operator_id for the sportsbook, not the user_id
        operator_id = session.get('operator_id')
        if not operator_id:
            return jsonify({"error": "Sportsbook operator not found"}), 401
        
        limit = request.args.get('limit', 500, type=int)  # Increased default from 100 to 500
        
        conn = None
        conn = get_tracked_connection()
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
        
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
    finally:
        if conn:
            conn.close()

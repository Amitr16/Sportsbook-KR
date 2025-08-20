"""
Comprehensive branding and customization system for sportsbook operators
"""

from flask import Blueprint, request, jsonify, render_template_string
import sqlite3
import json
import os
from datetime import datetime

branding_bp = Blueprint('branding', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_operator_branding(subdomain):
    """Get operator branding and customization settings"""
    conn = get_db_connection()
    
    operator = conn.execute("""
        SELECT 
            id, sportsbook_name, subdomain, email, is_active,
            settings, created_at
        FROM sportsbook_operators 
        WHERE subdomain = ? AND is_active = 1
    """, (subdomain,)).fetchone()
    
    conn.close()
    
    if not operator:
        return None
    
    # Parse settings or use defaults
    settings = json.loads(operator['settings']) if operator['settings'] else {}
    
    # Default branding settings
    default_branding = {
        'theme': {
            'primary_color': '#f39c12',
            'secondary_color': '#2c3e50',
            'accent_color': '#e74c3c',
            'background_color': '#1a1a1a',
            'text_color': '#ffffff',
            'card_background': '#2d3748',
            'success_color': '#27ae60',
            'warning_color': '#f39c12',
            'error_color': '#e74c3c'
        },
        'branding': {
            'logo_url': '',
            'favicon_url': '',
            'welcome_message': f'Welcome to {operator["sportsbook_name"]}',
            'footer_text': f'© 2025 {operator["sportsbook_name"]}. All rights reserved.',
            'contact_email': operator['email'] or 'support@sportsbook.com',
            'support_phone': '',
            'social_links': {
                'facebook': '',
                'twitter': '',
                'instagram': '',
                'telegram': ''
            }
        },
        'features': {
            'live_betting': True,
            'cash_out': True,
            'multi_bet': True,
            'live_streaming': False,
            'statistics': True,
            'promotions': True
        },
        'betting': {
            'default_currency': 'USD',
            'currency_symbol': '$',
            'odds_format': 'decimal',  # decimal, fractional, american
            'min_bet': 1.0,
            'max_bet': 10000.0,
            'max_payout': 100000.0,
            'commission_rate': 0.05
        },
        'layout': {
            'show_promotions_banner': True,
            'show_live_scores': True,
            'show_trending_events': True,
            'sidebar_position': 'left',  # left, right
            'compact_mode': False
        }
    }
    
    # Merge with operator's custom settings
    branding = default_branding.copy()
    if 'branding' in settings:
        branding.update(settings['branding'])
    
    # Add operator info
    branding['operator'] = {
        'id': operator['id'],
        'name': operator['sportsbook_name'],
        'subdomain': operator['subdomain'],
        'email': operator['email'],
        'created_at': operator['created_at']
    }
    
    return branding

def generate_custom_css(branding):
    """Generate custom CSS based on operator branding"""
    theme = branding.get('theme', {})
    
    css = f"""
    <style>
    :root {{
        --primary-color: {theme.get('primary_color', '#f39c12')};
        --secondary-color: {theme.get('secondary_color', '#2c3e50')};
        --accent-color: {theme.get('accent_color', '#e74c3c')};
        --background-color: {theme.get('background_color', '#1a1a1a')};
        --text-color: {theme.get('text_color', '#ffffff')};
        --card-background: {theme.get('card_background', '#2d3748')};
        --success-color: {theme.get('success_color', '#27ae60')};
        --warning-color: {theme.get('warning_color', '#f39c12')};
        --error-color: {theme.get('error_color', '#e74c3c')};
    }}
    
    /* Override default colors */
    body {{
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
    }}
    
    .navbar {{
        background-color: var(--secondary-color) !important;
    }}
    
    .btn-primary {{
        background-color: var(--primary-color) !important;
        border-color: var(--primary-color) !important;
    }}
    
    .btn-primary:hover {{
        background-color: var(--accent-color) !important;
        border-color: var(--accent-color) !important;
    }}
    
    .card {{
        background-color: var(--card-background) !important;
        border-color: var(--secondary-color) !important;
    }}
    
    .odds-button {{
        background-color: var(--primary-color) !important;
        color: white !important;
    }}
    
    .odds-button:hover {{
        background-color: var(--accent-color) !important;
    }}
    
    .text-success {{
        color: var(--success-color) !important;
    }}
    
    .text-warning {{
        color: var(--warning-color) !important;
    }}
    
    .text-danger {{
        color: var(--error-color) !important;
    }}
    
    /* Custom branding elements */
    .brand-logo {{
        max-height: 40px;
        width: auto;
    }}
    
    .welcome-banner {{
        background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
    }}
    
    .footer-custom {{
        background-color: var(--secondary-color);
        color: var(--text-color);
        padding: 20px 0;
        margin-top: 40px;
    }}
    
    .social-links a {{
        color: var(--primary-color);
        margin: 0 10px;
        font-size: 1.2em;
    }}
    
    .social-links a:hover {{
        color: var(--accent-color);
    }}
    </style>
    """
    
    return css

def generate_custom_js(branding):
    """Generate custom JavaScript for operator-specific functionality"""
    operator = branding.get('operator', {})
    betting = branding.get('betting', {})
    features = branding.get('features', {})
    
    js = f"""
    <script>
    // Operator context and branding
    window.OPERATOR_CONTEXT = {{
        id: {operator.get('id', 0)},
        name: '{operator.get('name', 'Sportsbook')}',
        subdomain: '{operator.get('subdomain', '')}',
        email: '{operator.get('email', '')}',
        branding: {json.dumps(branding)}
    }};
    
    // Betting configuration
    window.BETTING_CONFIG = {{
        currency: '{betting.get('default_currency', 'USD')}',
        currencySymbol: '{betting.get('currency_symbol', '$')}',
        oddsFormat: '{betting.get('odds_format', 'decimal')}',
        minBet: {betting.get('min_bet', 1.0)},
        maxBet: {betting.get('max_bet', 10000.0)},
        maxPayout: {betting.get('max_payout', 100000.0)}
    }};
    
    // Feature flags
    window.FEATURES = {{
        liveBetting: {str(features.get('live_betting', True)).lower()},
        cashOut: {str(features.get('cash_out', True)).lower()},
        multiBet: {str(features.get('multi_bet', True)).lower()},
        liveStreaming: {str(features.get('live_streaming', False)).lower()},
        statistics: {str(features.get('statistics', True)).lower()},
        promotions: {str(features.get('promotions', True)).lower()}
    }};
    
    // Initialize operator-specific functionality
    document.addEventListener('DOMContentLoaded', function() {{
        // Update page title
        document.title = window.OPERATOR_CONTEXT.name + ' - Sports Betting Platform';
        
        // Update favicon if provided
        const faviconUrl = window.OPERATOR_CONTEXT.branding.branding?.favicon_url;
        if (faviconUrl) {{
            const favicon = document.querySelector('link[rel="icon"]') || document.createElement('link');
            favicon.rel = 'icon';
            favicon.href = faviconUrl;
            document.head.appendChild(favicon);
        }}
        
        // Add welcome banner if enabled
        const welcomeMessage = window.OPERATOR_CONTEXT.branding.branding?.welcome_message;
        if (welcomeMessage) {{
            const banner = document.createElement('div');
            banner.className = 'welcome-banner';
            banner.innerHTML = '<h4>' + welcomeMessage + '</h4>';
            
            const container = document.querySelector('.container') || document.body;
            container.insertBefore(banner, container.firstChild);
        }}
        
        // Update logo if provided
        const logoUrl = window.OPERATOR_CONTEXT.branding.branding?.logo_url;
        if (logoUrl) {{
            const logos = document.querySelectorAll('.navbar-brand, .logo');
            logos.forEach(logo => {{
                logo.innerHTML = '<img src="' + logoUrl + '" alt="' + window.OPERATOR_CONTEXT.name + '" class="brand-logo">';
            }});
        }}
        
        // Add custom footer
        const footerText = window.OPERATOR_CONTEXT.branding.branding?.footer_text;
        if (footerText) {{
            const footer = document.createElement('footer');
            footer.className = 'footer-custom text-center';
            footer.innerHTML = '<div class="container"><p>' + footerText + '</p></div>';
            document.body.appendChild(footer);
        }}
        
        // Initialize currency formatting
        window.formatCurrency = function(amount) {{
            return window.BETTING_CONFIG.currencySymbol + parseFloat(amount).toFixed(2);
        }};
        
        // Initialize odds formatting
        window.formatOdds = function(odds) {{
            const format = window.BETTING_CONFIG.oddsFormat;
            switch(format) {{
                case 'fractional':
                    return convertToFractional(odds);
                case 'american':
                    return convertToAmerican(odds);
                default:
                    return parseFloat(odds).toFixed(2);
            }}
        }};
        
        function convertToFractional(decimal) {{
            const fraction = decimal - 1;
            // Simple fraction conversion (could be enhanced)
            return fraction.toFixed(2) + '/1';
        }}
        
        function convertToAmerican(decimal) {{
            if (decimal >= 2) {{
                return '+' + Math.round((decimal - 1) * 100);
            }} else {{
                return '-' + Math.round(100 / (decimal - 1));
            }}
        }}
        
        console.log('🎨 Operator branding initialized for:', window.OPERATOR_CONTEXT.name);
    }});
    </script>
    """
    
    return js

@branding_bp.route('/api/branding/<subdomain>')
def get_branding_api(subdomain):
    """API endpoint to get operator branding"""
    branding = get_operator_branding(subdomain)
    
    if not branding:
        return jsonify({
            'success': False,
            'error': 'Operator not found or inactive'
        }), 404
    
    return jsonify({
        'success': True,
        'branding': branding
    })

@branding_bp.route('/api/branding/<subdomain>/update', methods=['POST'])
def update_branding(subdomain):
    """Update operator branding settings"""
    try:
        # This would require admin authentication
        # For now, just return the structure
        
        data = request.get_json()
        
        conn = get_db_connection()
        
        # Get current settings
        operator = conn.execute("""
            SELECT id, settings FROM sportsbook_operators 
            WHERE subdomain = ?
        """, (subdomain,)).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404
        
        # Update settings
        current_settings = json.loads(operator['settings']) if operator['settings'] else {}
        current_settings.update(data)
        
        conn.execute("""
            UPDATE sportsbook_operators 
            SET settings = ?, updated_at = ?
            WHERE subdomain = ?
        """, (json.dumps(current_settings), datetime.utcnow(), subdomain))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Branding updated successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


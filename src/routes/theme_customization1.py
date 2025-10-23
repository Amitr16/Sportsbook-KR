"""
Theme Customization API Routes
Provides endpoints for theme templates, saving/loading customizations
"""

from flask import Blueprint, request, jsonify, session
from src import sqlite3_shim as sqlite3
import os
from datetime import datetime

theme_bp = Blueprint('theme', __name__)

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim with tracking"""
    from src.utils.connection_tracker import track_connection_acquired
    
    # Track this connection acquisition
    context, track_start = track_connection_acquired("theme_customization1.py::get_db_connection")
    
    # Try multiple possible database paths
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'database', 'app.db'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'app.db'),
        'src/database/app.db',
        'database/app.db'
    ]
    
    for db_path in possible_paths:
        if os.path.exists(db_path):
            print(f"✅ Using database at: {db_path}")
            from src.db_compat import connect
            conn = connect(use_pool=True, _skip_tracking=True)  # Skip tracking since we track manually
            conn.row_factory = sqlite3.Row
            conn._tracking_context = context
            conn._tracking_start = track_start
            return conn
    
    # If no path found, use the first one and let it fail with a clear error
    print(f"❌ No database found at any of these paths: {possible_paths}")
    raise FileNotFoundError(f"Database not found. Tried: {possible_paths}")

@theme_bp.route('/api/theme-templates', methods=['GET'])
def get_theme_templates():
    """Get all available theme templates"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM theme_templates 
            ORDER BY is_premium ASC, display_name ASC
        ''')
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                'id': row['id'],
                'template_name': row['template_name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'preview_image_url': row['preview_image_url'],
                'primary_color': row['primary_color'],
                'secondary_color': row['secondary_color'],
                'accent_color': row['accent_color'],
                'background_color': row['background_color'],
                'text_color': row['text_color'],
                'font_family': row['font_family'],
                'layout_style': row['layout_style'],
                'button_style': row['button_style'],
                'card_style': row['card_style'],
                'custom_css': row['custom_css'],
                'is_premium': bool(row['is_premium'])
            })
        
        conn.close()
        return jsonify(templates)
        
    except Exception as e:
        print(f"Error loading theme templates: {e}")
        return jsonify({'error': 'Failed to load theme templates'}), 500

@theme_bp.route('/api/save-theme', methods=['POST'])
def save_theme():
    """Save theme customization for current operator"""
    try:
        print("🔍 Starting theme save process...")
        
        # Get theme data from request
        theme_data = request.get_json()
        print(f"🔍 Received theme data: {theme_data}")
        
        if not theme_data:
            return jsonify({'error': 'No theme data provided'}), 400
        
        # For now, we'll use a default operator ID
        # In a real implementation, this would come from session/authentication
        operator_id = 1  # Default operator for testing
        print(f"🔍 Using operator_id: {operator_id}")
        
        # You could also get operator from session if admin is logged in
        if 'admin_id' in session:
            print(f"🔍 Admin ID in session: {session['admin_id']}")
            # Get operator ID from admin session
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT sportsbook_operator_id FROM sportsbook_operators WHERE id = ?', (session['admin_id'],))
            result = cursor.fetchone()
            if result:
                operator_id = result['sportsbook_operator_id']
                print(f"🔍 Updated operator_id from session: {operator_id}")
            conn.close()
        
        print("🔍 Getting database connection...")
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Database connection successful")
        
        # Create sportsbook_themes table if it doesn't exist
        print("🔍 Creating sportsbook_themes table if it doesn't exist...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sportsbook_themes (
                id SERIAL PRIMARY KEY,
                sportsbook_operator_id INTEGER NOT NULL,
                primary_color TEXT DEFAULT '#1e40af',
                secondary_color TEXT DEFAULT '#3b82f6',
                accent_color TEXT DEFAULT '#f59e0b',
                background_color TEXT DEFAULT '#ffffff',
                text_color TEXT DEFAULT '#1f2937',
                font_family TEXT DEFAULT 'Inter, sans-serif',
                layout_style TEXT DEFAULT 'modern',
                button_style TEXT DEFAULT 'rounded',
                card_style TEXT DEFAULT 'shadow',
                custom_css TEXT,
                logo_url TEXT,
                banner_image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators (id)
            )
        ''')
        print("✅ Table creation/check successful")
        
        # Check if theme customization already exists for this operator
        print(f"🔍 Checking for existing theme for operator_id: {operator_id}")
        cursor.execute('SELECT id FROM sportsbook_themes WHERE sportsbook_operator_id = ?', (operator_id,))
        existing = cursor.fetchone()
        print(f"🔍 Existing theme found: {existing is not None}")
        
        if existing:
            # Update existing theme
            print("🔍 Updating existing theme...")
            cursor.execute('''
                UPDATE sportsbook_themes SET
                    primary_color = ?,
                    secondary_color = ?,
                    accent_color = ?,
                    background_color = ?,
                    text_color = ?,
                    font_family = ?,
                    layout_style = ?,
                    button_style = ?,
                    card_style = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE sportsbook_operator_id = ?
            ''', (
                theme_data.get('primaryColor', '#1e40af'),
                theme_data.get('secondaryColor', '#3b82f6'),
                theme_data.get('accentColor', '#f59e0b'),
                theme_data.get('backgroundColor', '#ffffff'),
                theme_data.get('textColor', '#1f2937'),
                theme_data.get('fontFamily', 'Inter, sans-serif'),
                theme_data.get('layoutStyle', 'modern'),
                theme_data.get('buttonStyle', 'rounded'),
                theme_data.get('cardStyle', 'shadow'),
                operator_id
            ))
            print("✅ Theme update successful")
        else:
            # Create new theme customization
            print("🔍 Creating new theme...")
            cursor.execute('''
                INSERT INTO sportsbook_themes 
                (sportsbook_operator_id, primary_color, secondary_color, accent_color, 
                 background_color, text_color, font_family, layout_style, button_style, card_style)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operator_id,
                theme_data.get('primaryColor', '#1e40af'),
                theme_data.get('secondaryColor', '#3b82f6'),
                theme_data.get('accentColor', '#f59e0b'),
                theme_data.get('backgroundColor', '#ffffff'),
                theme_data.get('textColor', '#1f2937'),
                theme_data.get('fontFamily', 'Inter, sans-serif'),
                theme_data.get('layoutStyle', 'modern'),
                theme_data.get('buttonStyle', 'rounded'),
                theme_data.get('cardStyle', 'shadow')
            ))
            print("✅ Theme creation successful")
        
        print("🔍 Committing changes to database...")
        conn.commit()
        print("✅ Database commit successful")
        conn.close()
        print("✅ Database connection closed")
        
        return jsonify({'success': True, 'message': 'Theme saved successfully'})
        
    except Exception as e:
        print(f"Error saving theme: {e}")
        return jsonify({'error': 'Failed to save theme'}), 500

@theme_bp.route('/api/load-theme/<subdomain>', methods=['GET'])
def load_theme(subdomain):
    """Load theme customization for a specific operator"""
    from src.db_compat import connection_ctx
    
    try:
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                
                # Get operator ID from subdomain
                cursor.execute('SELECT id FROM sportsbook_operators WHERE subdomain = %s', (subdomain,))
                operator = cursor.fetchone()
                
                if not operator:
                    return jsonify({'error': 'Operator not found'}), 404
                
                # Get theme customization
                cursor.execute('''
                    SELECT * FROM sportsbook_themes 
                    WHERE sportsbook_operator_id = %s
                ''', (operator['id'],))
                
                theme = cursor.fetchone()
                
                if theme:
                    theme_data = {
                        'primaryColor': theme['primary_color'],
                        'secondaryColor': theme['secondary_color'],
                        'accentColor': theme['accent_color'],
                        'backgroundColor': theme['background_color'],
                        'textColor': theme['text_color'],
                        'fontFamily': theme['font_family'],
                        'layoutStyle': theme['layout_style'],
                        'buttonStyle': theme['button_style'],
                        'cardStyle': theme['card_style'],
                        'customCss': theme['custom_css'],
                        'logoUrl': theme['logo_url'],
                        'bannerImageUrl': theme['banner_image_url']
                    }
                else:
                    # Return default theme
                    theme_data = {
                        'primaryColor': '#1e40af',
                        'secondaryColor': '#3b82f6',
                        'accentColor': '#f59e0b',
                        'backgroundColor': '#ffffff',
                        'textColor': '#1f2937',
                        'fontFamily': 'Inter, sans-serif',
                        'layoutStyle': 'modern',
                        'buttonStyle': 'rounded',
                        'cardStyle': 'shadow',
                        'customCss': None,
                        'logoUrl': None,
                        'bannerImageUrl': None
                    }
                
                return jsonify(theme_data)
        
    except Exception as e:
        print(f"Error loading theme: {e}")
        return jsonify({'error': 'Failed to load theme'}), 500

@theme_bp.route('/api/save-theme/<subdomain>', methods=['POST'])
def save_theme_for_operator(subdomain):
    """Save theme customization for a specific operator"""
    from src.db_compat import connection_ctx
    
    try:
        # Get theme data from request
        theme_data = request.get_json()
        
        if not theme_data:
            return jsonify({'error': 'No theme data provided'}), 400
        
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                
                # Create sportsbook_themes table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sportsbook_themes (
                        id SERIAL PRIMARY KEY,
                        sportsbook_operator_id INTEGER NOT NULL,
                        primary_color TEXT DEFAULT '#1e40af',
                        secondary_color TEXT DEFAULT '#3b82f6',
                        accent_color TEXT DEFAULT '#f59e0b',
                        background_color TEXT DEFAULT '#ffffff',
                        text_color TEXT DEFAULT '#1f2937',
                        font_family TEXT DEFAULT 'Inter, sans-serif',
                        layout_style TEXT DEFAULT 'modern',
                        button_style TEXT DEFAULT 'rounded',
                        card_style TEXT DEFAULT 'shadow',
                        custom_css TEXT,
                        logo_url TEXT,
                        banner_image_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators (id)
                    )
                ''')
                
                # Get operator ID from subdomain
                cursor.execute('SELECT id FROM sportsbook_operators WHERE subdomain = %s', (subdomain,))
                operator = cursor.fetchone()
                
                if not operator:
                    return jsonify({'error': 'Operator not found'}), 404
                
                operator_id = operator['id']
                
                # Check if theme customization already exists for this operator
                cursor.execute('SELECT id FROM sportsbook_themes WHERE sportsbook_operator_id = %s', (operator_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing theme
                    cursor.execute('''
                        UPDATE sportsbook_themes SET
                            primary_color = %s,
                            secondary_color = %s,
                            accent_color = %s,
                            background_color = %s,
                            text_color = %s,
                            font_family = %s,
                            layout_style = %s,
                            button_style = %s,
                            card_style = %s,
                            custom_css = %s,
                            logo_url = %s,
                            banner_image_url = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE sportsbook_operator_id = %s
                    ''', (
                        theme_data.get('primaryColor', '#1e40af'),
                        theme_data.get('secondaryColor', '#3b82f6'),
                        theme_data.get('accentColor', '#f59e0b'),
                        theme_data.get('backgroundColor', '#ffffff'),
                        theme_data.get('textColor', '#1f2937'),
                        theme_data.get('fontFamily', 'Inter, sans-serif'),
                        theme_data.get('layoutStyle', 'modern'),
                        theme_data.get('buttonStyle', 'rounded'),
                        theme_data.get('cardStyle', 'shadow'),
                        theme_data.get('customCss'),
                        theme_data.get('logoUrl'),
                        theme_data.get('bannerImageUrl'),
                        operator_id
                    ))
                else:
                    # Create new theme customization
                    cursor.execute('''
                        INSERT INTO sportsbook_themes 
                        (sportsbook_operator_id, primary_color, secondary_color, accent_color, 
                         background_color, text_color, font_family, layout_style, button_style, 
                         card_style, custom_css, logo_url, banner_image_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        operator_id,
                        theme_data.get('primaryColor', '#1e40af'),
                        theme_data.get('secondaryColor', '#3b82f6'),
                        theme_data.get('accentColor', '#f59e0b'),
                        theme_data.get('backgroundColor', '#ffffff'),
                        theme_data.get('textColor', '#1f2937'),
                        theme_data.get('fontFamily', 'Inter, sans-serif'),
                        theme_data.get('layoutStyle', 'modern'),
                        theme_data.get('buttonStyle', 'rounded'),
                        theme_data.get('cardStyle', 'shadow'),
                        theme_data.get('customCss'),
                        theme_data.get('logoUrl'),
                        theme_data.get('bannerImageUrl')
                    ))
        
        return jsonify({'success': True, 'message': 'Theme saved successfully'})
        
    except Exception as e:
        print(f"Error saving theme: {e}")
        return jsonify({'error': 'Failed to save theme'}), 500

@theme_bp.route('/api/theme-css/<subdomain>', methods=['GET'])
def get_theme_css(subdomain):
    """Generate CSS for a specific operator's theme"""
    from src.db_compat import connection_ctx
    
    try:
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                
                # Get operator ID from subdomain
                cursor.execute('SELECT id FROM sportsbook_operators WHERE subdomain = %s', (subdomain,))
                operator = cursor.fetchone()
                
                if not operator:
                    return "/* Operator not found */", 404, {'Content-Type': 'text/css'}
                
                # Get theme customization
                cursor.execute('''
                    SELECT * FROM sportsbook_themes 
                    WHERE sportsbook_operator_id = %s
                ''', (operator['id'],))
                
                theme = cursor.fetchone()
                
                if not theme:
                    # Return default CSS
                    css = """
                    :root {
                        --primary-color: #1e40af;
                        --secondary-color: #3b82f6;
                        --accent-color: #f59e0b;
                        --background-color: #ffffff;
                        --text-color: #1f2937;
                        --font-family: 'Inter', sans-serif;
                    }
                    """
                else:
                    # Generate CSS from theme
                    css = f"""
                    :root {{
                        --primary-color: {theme['primary_color']};
                        --secondary-color: {theme['secondary_color']};
                        --accent-color: {theme['accent_color']};
                        --background-color: {theme['background_color']};
                        --text-color: {theme['text_color']};
                        --font-family: {theme['font_family']};
                    }}
                    
                    body {{
                        font-family: var(--font-family);
                        color: var(--text-color);
                        background-color: var(--background-color);
                    }}
                    
                    .btn-primary {{
                        background-color: var(--primary-color);
                        border-color: var(--primary-color);
                    }}
                    
                    .btn-secondary {{
                        background-color: var(--secondary-color);
                        border-color: var(--secondary-color);
                    }}
                    
                    .btn-accent {{
                        background-color: var(--accent-color);
                        border-color: var(--accent-color);
                    }}
                    
                    .text-primary {{
                        color: var(--primary-color);
                    }}
                    
                    .text-secondary {{
                        color: var(--secondary-color);
                    }}
                    
                    .text-accent {{
                        color: var(--accent-color);
                    }}
                    
                    .bg-primary {{
                        background-color: var(--primary-color);
                    }}
                    
                    .bg-secondary {{
                        background-color: var(--secondary-color);
                    }}
                    
                    .bg-accent {{
                        background-color: var(--accent-color);
                    }}
                    """
                    
                    # Add custom CSS if available
                    if theme['custom_css']:
                        css += f"\n\n/* Custom CSS */\n{theme['custom_css']}"
                
                return css, 200, {'Content-Type': 'text/css'}
        
    except Exception as e:
        print(f"Error generating theme CSS: {e}")
        return "/* Error generating CSS */", 500, {'Content-Type': 'text/css'}

@theme_bp.route('/theme-customizer')
def theme_customizer():
    """Serve the theme customizer page"""
    try:
        # Read the theme customizer HTML file
        html_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'theme-customizer.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return html_content, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        print(f"Error serving theme customizer: {e}")
        return "Theme customizer not available", 500

@theme_bp.route('/api/operator-themes', methods=['GET'])
def get_all_operator_themes():
    """Get themes for all operators (for super admin)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                so.id,
                so.sportsbook_name,
                so.subdomain,
                st.primary_color,
                st.secondary_color,
                st.accent_color,
                st.background_color,
                st.text_color,
                st.font_family,
                st.layout_style,
                st.button_style,
                st.card_style,
                st.updated_at
            FROM sportsbook_operators so
            LEFT JOIN sportsbook_themes st ON so.id = st.sportsbook_operator_id
            ORDER BY so.sportsbook_name
        ''')
        
        themes = []
        for row in cursor.fetchall():
            themes.append({
                'operator_id': row['id'],
                'sportsbook_name': row['sportsbook_name'],
                'subdomain': row['subdomain'],
                'theme': {
                    'primaryColor': row['primary_color'] or '#1e40af',
                    'secondaryColor': row['secondary_color'] or '#3b82f6',
                    'accentColor': row['accent_color'] or '#f59e0b',
                    'backgroundColor': row['background_color'] or '#ffffff',
                    'textColor': row['text_color'] or '#1f2937',
                    'fontFamily': row['font_family'] or 'Inter, sans-serif',
                    'layoutStyle': row['layout_style'] or 'modern',
                    'buttonStyle': row['button_style'] or 'rounded',
                    'cardStyle': row['card_style'] or 'shadow'
                },
                'updated_at': row['updated_at']
            })
        
        conn.close()
        return jsonify(themes)
        
    except Exception as e:
        print(f"Error loading operator themes: {e}")
        return jsonify({'error': 'Failed to load operator themes'}), 500


@theme_bp.route('/api/branding/<subdomain>', methods=['GET'])
def get_branding(subdomain):
    """Get branding information for a specific subdomain"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                so.sportsbook_name,
                st.logo_type,
                st.logo_url,
                st.sportsbook_name as custom_name
            FROM sportsbook_operators so
            LEFT JOIN sportsbook_themes st ON so.id = st.sportsbook_operator_id
            WHERE so.subdomain = ?
        ''', (subdomain,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                'sportsbook_name': row['custom_name'] or row['sportsbook_name'],
                'logo_type': row['logo_type'] or 'default',
                'logo_url': row['logo_url']
            })
        else:
            return jsonify({'error': 'Operator not found'}), 404
            
    except Exception as e:
        print(f"Error loading branding for {subdomain}: {e}")
        return jsonify({'error': 'Failed to load branding'}), 500


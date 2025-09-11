#!/usr/bin/env python3
"""
Export Pending Bets to CSV
Exports all pending bets from the database to a downloadable CSV file
"""

import os
import sys
import csv
import io
from datetime import datetime
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables"""
    # Try different environment variable names
    db_url = os.getenv('DATABASE_URL') or os.getenv('DB_URL') or os.getenv('POSTGRES_URL')
    
    if not db_url:
        # Fallback to local development
        db_url = "postgresql://postgres:password@localhost:5432/goalserve_sportsbook"
        logger.warning("No DATABASE_URL found, using local development database")
    
    return db_url

def create_app():
    """Create Flask app for database access"""
    app = Flask(__name__)
    
    # Set up database
    db_url = get_database_url()
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

def export_pending_bets_to_csv():
    """Export all pending bets to CSV format"""
    try:
        app = create_app()
        
        # Create database engine
        db_url = get_database_url()
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔍 Fetching pending bets from database...")
        
        # Query to get all pending bets with their details
        query = text("""
            SELECT 
                b.id,
                b.user_id,
                b.match_id,
                b.match_name,
                b.selection,
                b.bet_selection,
                b.stake,
                b.odds,
                b.combo_selections,
                b.created_at,
                b.updated_at,
                u.username,
                u.email
            FROM bets b
            LEFT JOIN users u ON b.user_id = u.id
            WHERE b.status = 'pending'
            ORDER BY b.created_at DESC
        """)
        
        result = session.execute(query)
        pending_bets = result.fetchall()
        
        logger.info(f"📊 Found {len(pending_bets)} pending bets")
        
        if not pending_bets:
            logger.info("No pending bets found")
            return None
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'Bet ID',
            'User ID', 
            'Username',
            'Email',
            'Match ID',
            'Match Name',
            'Selection',
            'Bet Selection',
            'Stake',
            'Odds',
            'Combo Selections',
            'Created At',
            'Updated At'
        ]
        writer.writerow(headers)
        
        # Write data rows
        for bet in pending_bets:
            # Parse combo_selections if it's JSON
            combo_selections_str = ""
            if bet.combo_selections:
                try:
                    import json
                    combo_data = json.loads(bet.combo_selections)
                    combo_selections_str = json.dumps(combo_data, indent=2)
                except:
                    combo_selections_str = str(bet.combo_selections)
            
            row = [
                bet.id,
                bet.user_id,
                bet.username or 'N/A',
                bet.email or 'N/A',
                bet.match_id or 'N/A',
                bet.match_name or 'N/A',
                bet.selection or 'N/A',
                bet.bet_selection or 'N/A',
                bet.stake or 0,
                bet.odds or 0,
                combo_selections_str,
                bet.created_at.isoformat() if bet.created_at else 'N/A',
                bet.updated_at.isoformat() if bet.updated_at else 'N/A'
            ]
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pending_bets_export_{timestamp}.csv"
        
        logger.info(f"✅ Successfully exported {len(pending_bets)} pending bets to CSV")
        logger.info(f"📁 Filename: {filename}")
        
        return csv_content, filename
        
    except Exception as e:
        logger.error(f"❌ Error exporting pending bets: {e}")
        return None, None
    finally:
        if 'session' in locals():
            session.close()

def save_csv_to_file(csv_content, filename):
    """Save CSV content to a file"""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            f.write(csv_content)
        logger.info(f"💾 CSV saved to: {filename}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving CSV file: {e}")
        return False

def main():
    """Main function to run the export"""
    logger.info("🚀 Starting pending bets export...")
    
    csv_content, filename = export_pending_bets_to_csv()
    
    if csv_content and filename:
        # Save to file
        if save_csv_to_file(csv_content, filename):
            logger.info("✅ Export completed successfully!")
            print(f"\n📊 Export Summary:")
            print(f"   File: {filename}")
            print(f"   Size: {len(csv_content)} characters")
            print(f"   Location: {os.path.abspath(filename)}")
        else:
            logger.error("❌ Failed to save CSV file")
    else:
        logger.error("❌ Export failed")

if __name__ == "__main__":
    main()

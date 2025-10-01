#!/usr/bin/env python3
"""
Quick test - just check if Flask is running and test registration
"""

import requests
import json

def quick_test():
    print("🚀 Quick System Test")
    print("=" * 40)
    
    # Test Flask app
    try:
        response = requests.get("http://localhost:5000/register-sportsbook", timeout=5)
        if response.status_code == 200:
            print("✅ Flask app running")
            print("✅ Registration page accessible")
            print("🌐 Visit: http://localhost:5000/register-sportsbook")
            return True
        else:
            print(f"❌ Flask issue: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Flask not running: {e}")
        print("💡 Start with: export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
        return False

if __name__ == "__main__":
    quick_test()

#!/bin/bash
# Automated Installation Script for Wallet Revenue Architecture
# This script installs the complete wallet system into your existing sportsbook project

set -e

echo "🚀 Installing Wallet Revenue Architecture System..."
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "src/main.py" ] || [ ! -f "src/routes/sportsbook_registration.py" ]; then
    echo "❌ Error: Please run this script from your goalserve-local1 project root directory"
    echo "   Expected files: src/main.py, src/routes/sportsbook_registration.py"
    exit 1
fi

# Check if database exists
if [ ! -f "src/database/app.db" ]; then
    echo "❌ Error: Database file src/database/app.db not found"
    echo "   Please ensure your Flask application has been initialized"
    exit 1
fi

echo "✓ Project structure validated"

# Backup existing registration file
echo "📦 Creating backup of existing registration file..."
cp src/routes/sportsbook_registration.py src/routes/sportsbook_registration.py.backup.$(date +%Y%m%d_%H%M%S)
echo "✓ Backup created"

# Apply database migration
echo "🗄️  Applying database migration..."
if sqlite3 src/database/app.db < wallet_migration.sql; then
    echo "✓ Database migration applied successfully"
else
    echo "❌ Database migration failed"
    exit 1
fi

# Update registration system
echo "🔄 Updating registration system..."
cp updated_sportsbook_registration.py src/routes/sportsbook_registration.py
echo "✓ Registration system updated"

# Copy service files
echo "⚙️  Installing revenue calculation service..."
cp end_of_day_revenue_service.py ./
cp setup_revenue_service.sh ./
chmod +x end_of_day_revenue_service.py
chmod +x setup_revenue_service.sh
echo "✓ Service files installed"

# Setup automated execution
echo "⏰ Setting up automated daily execution..."
if ./setup_revenue_service.sh; then
    echo "✓ Automated execution configured"
else
    echo "⚠️  Automated setup failed, but you can run manually"
fi

# Copy test files
echo "🧪 Installing test suite..."
cp test_wallet_system.py ./
chmod +x test_wallet_system.py
echo "✓ Test suite installed"

# Run tests
echo "🔍 Running system validation tests..."
if python3 test_wallet_system.py --database src/database/app.db; then
    echo "✅ All tests passed! System is ready to use."
else
    echo "⚠️  Some tests failed. Please review the output above."
fi

echo ""
echo "🎉 Installation Complete!"
echo "======================="
echo ""
echo "Next steps:"
echo "1. Restart your Flask application"
echo "2. Test registration at: http://localhost:5000/static/register-sportsbook.html"
echo "3. Check that 4 wallets are created for new operators"
echo "4. Review the implementation guide: WALLET_IMPLEMENTATION_GUIDE.md"
echo ""
echo "Manual revenue calculation:"
echo "  ./run_revenue_calculation.sh"
echo ""
echo "Service management:"
echo "  sudo systemctl status revenue-calculation.timer"
echo "  sudo journalctl -u revenue-calculation.service"
echo ""
echo "For detailed documentation, see: WALLET_IMPLEMENTATION_GUIDE.md"


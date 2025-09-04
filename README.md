# 🏆 Kryzel Sports Betting Platform

A comprehensive, multi-tenant sports betting platform built with Flask, featuring automated revenue management, real-time odds, and complete admin controls.

## 🌟 Features

### 🎯 Core Platform
- **Multi-tenant Architecture** - Each operator gets their own branded subdomain
- **Real-time Sports Odds** - Live odds from multiple sports (Soccer, Basketball, Tennis, etc.)
- **Automated Bet Settlement** - AI-powered match result detection and bet processing
- **Revenue Management** - Automated daily revenue calculations and wallet updates
- **Admin Dashboards** - Comprehensive operator and superadmin interfaces

### 💰 Revenue System
- **Daily Revenue Calculator** - Automated daily profit/loss calculations
- **Operator Wallet Management** - Automatic wallet updates with surplus handling
- **Revenue Distribution** - Smart profit sharing between bookmaker and community
- **Negative Revenue Protection** - Safe handling of loss days with wallet caps

### 🎨 Branding & Customization
- **Custom Themes** - Each operator can customize their platform appearance
- **White-label Solution** - Complete branding control for operators
- **Responsive Design** - Mobile-first, modern UI/UX

### 🔒 Security & Authentication
- **Multi-level Authentication** - User, Admin, and Superadmin access levels
- **Session Management** - Secure session handling with Redis
- **CORS Protection** - Configurable cross-origin resource sharing
- **Environment-based Configuration** - Secure secret management

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Redis (optional, for session management)
- Node.js 16+ (for frontend deployment)

### 1. Clone the Repository
```bash
git clone https://github.com/Amitr16/Sportsbook-KR.git
cd Sportsbook-KR
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup
```bash
# Copy environment template
cp env.example env.local

# Edit environment variables
nano env.local
```

Required environment variables:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/kryzel_sportsbook
SECRET_KEY=your-secret-key-here
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### 4. Database Setup
```bash
# Run database migrations
python setup_database.py

# Or for local development
python setup_local_db.py
```

### 5. Start the Application
```bash
# Development mode
python run.py

# Or using the local runner
python run_local.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
kryzel-sportsbook/
├── src/                          # Main application code
│   ├── routes/                   # Flask route handlers
│   │   ├── auth.py              # Authentication routes
│   │   ├── betting.py           # Betting functionality
│   │   ├── rich_admin_interface.py  # Admin dashboard
│   │   └── ...
│   ├── static/                   # Frontend assets
│   │   ├── index.html           # Main betting interface
│   │   ├── admin-dashboard.html # Admin panel
│   │   └── register-sportsbook.html
│   ├── models/                   # Database models
│   ├── services/                 # Business logic services
│   └── main.py                   # Flask application entry point
├── frontend/                     # Cloudflare Pages frontend
├── daily_revenue_calculator.py   # Daily revenue automation
├── update_operator_wallets.py    # Wallet management automation
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## 🔧 Configuration

### Database Configuration
The platform supports both SQLite (development) and PostgreSQL (production):

```python
# SQLite (default for development)
DATABASE_URL = "sqlite:///local_app.db"

# PostgreSQL (production)
DATABASE_URL = "postgresql://user:password@host:port/database"
```

### Multi-tenant Setup
Each operator gets their own subdomain:
- `megabook.yourdomain.com` - Operator subdomain
- `admin.yourdomain.com` - Admin interface
- `superadmin.yourdomain.com` - Superadmin interface

## 💼 Revenue Management

### Daily Revenue Calculator
Automated daily revenue calculations with smart distribution:

```bash
# Run daily revenue calculations
python daily_revenue_calculator.py

# Or use the batch script
run_daily_revenue.bat  # Windows
./run_daily_revenue.ps1  # PowerShell
```

### Operator Wallet Updates
Process revenue distributions and update operator wallets:

```bash
# Update operator wallets
python update_operator_wallets.py

# Or use the batch script
run_wallet_updates.bat  # Windows
./run_wallet_updates.ps1  # PowerShell
```

### Revenue Distribution Logic
- **Profit Days**: 90% to bookmaker, 10% to Kryzel, 30% to community
- **Loss Days**: 95% to bookmaker, 0% to Kryzel, 35% to community
- **Wallet Protection**: Bookmaker capital capped at $10,000, surplus goes to revenue wallet

## 🚀 Deployment

### Frontend (Cloudflare Pages)
```bash
cd frontend
npm install
npm run build
wrangler pages deploy
```

### Backend (Fly.io)
```bash
# Deploy to Fly.io
fly deploy

# Or use the deployment script
./deploy.sh
```

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d
```

## 📊 Admin Features

### Operator Dashboard
- Real-time betting statistics
- Manual bet settlement
- Revenue tracking
- User management
- Theme customization

### Superadmin Dashboard
- Multi-operator management
- Global bet settlement
- System-wide analytics
- Operator wallet management
- Revenue distribution oversight

## 🔌 API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/logout` - User logout

### Betting
- `GET /api/sports` - Get available sports
- `GET /api/odds/{sport}` - Get odds for sport
- `POST /api/place-bet` - Place a bet
- `GET /api/bets` - Get user bets

### Admin
- `GET /admin/dashboard` - Admin dashboard
- `POST /admin/settle-bet` - Manual bet settlement
- `GET /admin/revenue` - Revenue analytics

## 🛠️ Development

### Local Development
```bash
# Start development server
python run_local.py

# Run with live reload
python -m flask run --debug
```

### Testing
```bash
# Run tests
python -m pytest tests/

# Test specific functionality
python test_local.py
```

### Database Migrations
```bash
# Create new migration
python create_postgres_schema.py

# Apply migrations
python migrate_to_fly.py
```

## 📈 Monitoring & Analytics

### Revenue Tracking
- Daily profit/loss calculations
- Operator performance metrics
- Community share distributions
- Historical revenue data

### Betting Analytics
- Real-time betting volume
- Popular sports and markets
- User betting patterns
- Settlement accuracy metrics

## 🔒 Security Features

- **Environment Variables** - All secrets stored in environment variables
- **CORS Protection** - Configurable cross-origin policies
- **Session Security** - Secure session management
- **Input Validation** - Comprehensive input sanitization
- **SQL Injection Protection** - Parameterized queries

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Database Setup](DATABASE_SETUP_README.md)
- [Frontend Deployment](FRONTEND_DEPLOYMENT_GUIDE.md)
- [PostgreSQL Migration](POSTGRESQL_MIGRATION_GUIDE.md)
- [Local Development](LOCAL_DEVELOPMENT.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation in the `/docs` folder
- Review the deployment guides for setup help

## 🎯 Roadmap

- [ ] Mobile app development
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Advanced betting markets
- [ ] Real-time notifications
- [ ] API rate limiting
- [ ] Advanced security features

---

**Built with ❤️ by the Kryzel Team**

*Empowering sports betting operators with cutting-edge technology and automated revenue management.*
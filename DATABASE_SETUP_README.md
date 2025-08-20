# GoalServe Sports Betting Platform - Database & Environment Setup

This document provides comprehensive instructions for setting up the database and environment configuration for the GoalServe Sports Betting Platform.

## 📁 Files Overview

### 1. Environment Configuration
- **`env_template.txt`** - Template for environment variables (copy to `.env`)
- **`.env`** - Your actual environment configuration file (create from template)

### 2. Database Schema
- **`complete_database_schema.sql`** - Complete SQL schema with all tables, indexes, and sample data
- **`setup_database.py`** - Python script to automatically set up the database

### 3. Documentation
- **`database_schema_design.md`** - Original database design documentation
- **`DATABASE_SETUP_README.md`** - This file

## 🚀 Quick Setup

### Step 1: Environment Configuration

1. **Copy the environment template:**
   ```bash
   cp env_template.txt .env
   ```

2. **Edit the `.env` file** with your specific configuration:
   ```bash
   # Edit .env file with your preferred text editor
   nano .env
   # or
   code .env
   ```

3. **Key configuration sections to review:**
   - Flask settings (host, port, debug mode)
   - Security keys (change in production)
   - Google OAuth credentials
   - Database connection
   - GoalServe API settings

### Step 2: Database Setup

#### Option A: Automatic Setup (Recommended)
```bash
python setup_database.py
```

This script will:
- Create the database directory structure
- Create all tables with proper relationships
- Add performance indexes
- Insert sample data
- Create useful database views
- Set up default admin accounts

#### Option B: Manual SQL Setup
```bash
# Navigate to the database directory
cd src/database

# Create the database
sqlite3 app.db < ../../complete_database_schema.sql
```

### Step 3: Verify Setup

1. **Check database creation:**
   ```bash
   ls -la src/database/
   # Should show: app.db, app.db-shm, app.db-wal
   ```

2. **Test database connection:**
   ```bash
   sqlite3 src/database/app.db
   .tables
   .quit
   ```

## 🗄️ Database Schema Overview

### Core Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `sportsbook_operators` | Multi-tenant sportsbook operators | Subdomain routing, commission rates |
| `super_admins` | Global platform administrators | Full system access |
| `users` | End-user accounts | Multi-tenant isolation, balance tracking |
| `bets` | User betting records | Multi-tenant, settlement tracking |
| `transactions` | Financial transactions | Balance updates, audit trail |
| `bet_slips` | Bet combinations | Multi-bet management |
| `sports` | Available sports | Icons, draw support, priority ordering |
| `matches` | Sporting events | Scores, status, team information |
| `odds` | Betting odds | Market types, selection options |
| `themes` | Branding customization | Colors, fonts, logos |

### Multi-Tenant Architecture

The platform supports multiple sportsbook operators, each with:
- **Isolated data** - Users, bets, and transactions are separated by operator
- **Custom branding** - Individual themes and styling
- **Independent revenue** - Separate commission tracking and financials
- **Subdomain routing** - Each operator gets their own URL structure

### Key Relationships

```
sportsbook_operators (1) ←→ (many) users
sportsbook_operators (1) ←→ (many) bets
sportsbook_operators (1) ←→ (many) transactions
users (1) ←→ (many) bets
users (1) ←→ (many) transactions
bets (many) ←→ (many) bet_slips (via bet_slip_bets)
```

## 🔐 Default Accounts

After running the setup script, you'll have these default accounts:

### Super Admin
- **Username:** `superadmin`
- **Password:** `superadmin123`
- **Email:** `admin@goalserve.com`
- **Access:** Full system administration

### Default Sportsbook Operator
- **Username:** `admin`
- **Password:** `admin123`
- **Subdomain:** `default`
- **Email:** `admin@default.com`
- **Access:** Sportsbook-specific administration

## 🎯 Database Features

### Performance Optimizations
- **Indexes** on all foreign keys and frequently queried fields
- **WAL mode** for better concurrency
- **Memory caching** for temporary operations
- **Optimized queries** with proper JOINs

### Data Integrity
- **Foreign key constraints** ensure referential integrity
- **Triggers** automatically update related data
- **Transaction support** for atomic operations
- **Audit trails** for all financial transactions

### Views for Analytics
- **`active_bets_view`** - Current pending bets with user info
- **`operator_revenue_view`** - Revenue summary by operator

## 🔧 Customization Options

### Adding New Sports
```sql
INSERT INTO sports (sport_key, sport_name, display_name, icon, has_draw, priority) 
VALUES ('new_sport', 'New Sport', 'New Sport Display', '🏆', 1, 19);
```

### Customizing Themes
```sql
UPDATE themes 
SET primary_color = '#ff0000', secondary_color = '#00ff00' 
WHERE sportsbook_operator_id = 1;
```

### Modifying Commission Rates
```sql
UPDATE sportsbook_operators 
SET commission_rate = 0.07 
WHERE id = 1;
```

## 🚨 Production Considerations

### Security
1. **Change default passwords** immediately
2. **Use strong SECRET_KEY** values
3. **Enable HTTPS** in production
4. **Restrict database access** to application only

### Performance
1. **Consider PostgreSQL** for high-traffic deployments
2. **Implement connection pooling**
3. **Add Redis** for session storage
4. **Monitor query performance**

### Backup
1. **Regular database backups**
2. **Test restore procedures**
3. **Version control** for schema changes
4. **Migration scripts** for updates

## 🐛 Troubleshooting

### Common Issues

1. **Database locked error:**
   ```bash
   # Check for other processes using the database
   lsof src/database/app.db
   ```

2. **Permission denied:**
   ```bash
   # Ensure proper file permissions
   chmod 644 src/database/app.db
   ```

3. **Foreign key constraint failed:**
   ```bash
   # Verify foreign key support is enabled
   sqlite3 src/database/app.db "PRAGMA foreign_keys;"
   ```

### Reset Database
```bash
# Remove existing database
rm src/database/app.db*

# Run setup script again
python setup_database.py
```

## 📚 Additional Resources

- **Flask-SQLAlchemy Documentation:** https://flask-sqlalchemy.palletsprojects.com/
- **SQLite Documentation:** https://www.sqlite.org/docs.html
- **Multi-Tenant Architecture Guide:** See `database_schema_design.md`

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the database schema design document
3. Check application logs in `app.log`
4. Verify environment configuration in `.env`

---

**Note:** This setup provides a production-ready foundation for the GoalServe Sports Betting Platform. Remember to customize configurations and security settings according to your specific deployment requirements.

# PostgreSQL Migration Guide for GoalServe Sports Betting Platform

## 🎯 Overview

This guide will help you migrate your GoalServe Sports Betting Platform from SQLite to PostgreSQL for better performance, scalability, and production readiness.

## 🚀 Benefits of PostgreSQL Migration

### **Performance Improvements**
- **Better concurrency** - Handles multiple users simultaneously
- **Advanced indexing** - Faster queries on large datasets
- **Connection pooling** - Efficient database connections
- **Query optimization** - Better query execution plans

### **Production Features**
- **ACID compliance** - Data integrity guarantees
- **Backup and recovery** - Professional database management
- **Replication** - High availability options
- **Monitoring** - Built-in performance metrics

### **Scalability**
- **Larger datasets** - Handle millions of records
- **Multiple connections** - Support high-traffic applications
- **Advanced data types** - Better data modeling

## 📋 Migration Steps

### **Step 1: Install PostgreSQL Dependencies**

```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
python -c "import psycopg2; print('PostgreSQL driver installed')"
```

### **Step 2: Set Up PostgreSQL Database**

#### **Option A: Local PostgreSQL Installation**

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# macOS (using Homebrew)
brew install postgresql
brew services start postgresql

# Windows
# Download from https://www.postgresql.org/download/windows/
```

#### **Option B: Cloud PostgreSQL (Recommended for Production)**

- **AWS RDS**: Managed PostgreSQL service
- **Google Cloud SQL**: Cloud-hosted PostgreSQL
- **Azure Database**: Microsoft's managed service
- **DigitalOcean**: Simple managed databases

### **Step 3: Create PostgreSQL Database**

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE goalserve_sportsbook;
CREATE USER goalserve_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE goalserve_sportsbook TO goalserve_user;
\q
```

### **Step 4: Update Environment Configuration**

Create or update your `.env` file:

```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=goalserve_sportsbook
POSTGRES_USER=goalserve_user
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Keep SQLite as fallback for development
# DATABASE_URL=sqlite:///src/database/app.db
```

### **Step 5: Update Application Configuration**

```bash
# Run the configuration update script
python update_database_config.py
```

This will:
- Update `src/main.py` to support PostgreSQL
- Update `src/models/__init__.py` for database initialization
- Create `src/database_config.py` for connection management

### **Step 6: Run the Migration**

```bash
# Execute the migration script
python migrate_to_postgresql.py
```

The migration script will:
1. **Test PostgreSQL connection**
2. **Create database schema**
3. **Migrate all data** from SQLite
4. **Create performance indexes**
5. **Verify data integrity**

### **Step 7: Test the Application**

```bash
# Test database connection
python -c "from src.database_config import test_database_connection; print('Connection:', test_database_connection())"

# Start your Flask application
python run.py
```

## 🔧 Configuration Details

### **Database Connection String Format**

```bash
# Local PostgreSQL
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# Cloud PostgreSQL (example: AWS RDS)
DATABASE_URL=postgresql://username:password@your-instance.region.rds.amazonaws.com:5432/database_name

# With SSL (production)
DATABASE_URL=postgresql://username:password@host:port/database_name?sslmode=require
```

### **Environment Variables**

```bash
# Required for PostgreSQL
POSTGRES_HOST=your_postgres_host
POSTGRES_PORT=5432
POSTGRES_DB=goalserve_sportsbook
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_secure_password

# Optional: Connection pooling
POSTGRES_POOL_SIZE=10
POSTGRES_MAX_OVERFLOW=20
POSTGRES_POOL_RECYCLE=300
```

## 🚨 Important Considerations

### **Data Backup**
- **Always backup** your SQLite database before migration
- **Test migration** on a copy of your data first
- **Verify data integrity** after migration

### **Performance Tuning**
- **Connection pooling** - Configure based on your traffic
- **Index optimization** - Monitor query performance
- **Regular maintenance** - VACUUM and ANALYZE tables

### **Security**
- **Use strong passwords** for database users
- **Limit network access** to database server
- **Enable SSL** for production connections
- **Regular security updates**

## 🔍 Troubleshooting

### **Common Issues**

#### **Connection Refused**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Verify port is open
netstat -an | grep 5432
```

#### **Authentication Failed**
```bash
# Check pg_hba.conf configuration
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Restart PostgreSQL after changes
sudo systemctl restart postgresql
```

#### **Permission Denied**
```bash
# Verify user permissions
sudo -u postgres psql -c "\\du"

# Grant necessary privileges
GRANT ALL PRIVILEGES ON DATABASE goalserve_sportsbook TO your_user;
```

### **Migration Issues**

#### **Data Type Conversion**
- The migration script handles most type conversions automatically
- Check logs for any conversion warnings
- Verify data integrity after migration

#### **Large Dataset Migration**
- For very large datasets, consider using `pg_dump` and `pg_restore`
- Monitor migration progress in the logs
- Consider running migration during low-traffic periods

## 📊 Performance Monitoring

### **PostgreSQL Monitoring Commands**

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Monitor query performance
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

-- Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### **Application Monitoring**

- **Database response times** in your API logs
- **Connection pool usage** statistics
- **Query execution times** for slow operations

## 🎉 Post-Migration Checklist

- [ ] **Database connection** working
- [ ] **All APIs responding** correctly
- [ ] **Data integrity** verified
- [ ] **Performance** improved
- [ ] **Backup procedures** configured
- [ ] **Monitoring** set up
- [ ] **Documentation** updated

## 🚀 Next Steps

After successful migration:

1. **Remove SQLite database** (keep as backup)
2. **Update deployment scripts** for PostgreSQL
3. **Configure database backups**
4. **Set up monitoring and alerting**
5. **Performance test** your application
6. **Update team documentation**

## 📞 Support

If you encounter issues during migration:

1. **Check the logs** from migration scripts
2. **Verify PostgreSQL configuration**
3. **Test database connectivity**
4. **Review error messages** carefully
5. **Check this guide** for common solutions

---

**Note**: This migration maintains backward compatibility. Your application will work with both SQLite and PostgreSQL based on your environment configuration.

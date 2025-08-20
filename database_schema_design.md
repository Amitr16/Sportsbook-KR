# Multi-Tenant Database Schema Design for GoalServe Super Admin

## Overview
This document outlines the database schema extensions needed to support multi-tenant architecture with sportsbook operators and super admin functionality.

## New Tables

### 1. sportsbook_operators
This table stores information about each sportsbook operator (admin) who registers to run their own betting site.

```sql
CREATE TABLE sportsbook_operators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sportsbook_name VARCHAR(100) NOT NULL UNIQUE,
    login VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120),
    subdomain VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    total_revenue FLOAT DEFAULT 0.0,
    commission_rate FLOAT DEFAULT 0.05,
    settings TEXT -- JSON field for operator-specific settings
);
```

### 2. super_admins
This table stores super admin credentials for global management.

```sql
CREATE TABLE super_admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    permissions TEXT -- JSON field for granular permissions
);
```

## Modified Tables

### 1. users table
Add sportsbook_operator_id to associate users with specific sportsbook operators.

```sql
ALTER TABLE users ADD COLUMN sportsbook_operator_id INTEGER;
ALTER TABLE users ADD FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id);
```

### 2. bets table
Add sportsbook_operator_id to track which operator the bet belongs to.

```sql
ALTER TABLE bets ADD COLUMN sportsbook_operator_id INTEGER;
ALTER TABLE bets ADD FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id);
```

### 3. transactions table
Add sportsbook_operator_id to track financial transactions by operator.

```sql
ALTER TABLE transactions ADD COLUMN sportsbook_operator_id INTEGER;
ALTER TABLE transactions ADD FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id);
```

### 4. bet_slips table
Add sportsbook_operator_id to track bet slips by operator.

```sql
ALTER TABLE bet_slips ADD COLUMN sportsbook_operator_id INTEGER;
ALTER TABLE bet_slips ADD FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id);
```

## New Indexes for Performance

```sql
CREATE INDEX idx_users_sportsbook_operator ON users(sportsbook_operator_id);
CREATE INDEX idx_bets_sportsbook_operator ON bets(sportsbook_operator_id);
CREATE INDEX idx_transactions_sportsbook_operator ON transactions(sportsbook_operator_id);
CREATE INDEX idx_bet_slips_sportsbook_operator ON bet_slips(sportsbook_operator_id);
CREATE INDEX idx_sportsbook_operators_subdomain ON sportsbook_operators(subdomain);
CREATE INDEX idx_sportsbook_operators_login ON sportsbook_operators(login);
```

## Data Relationships

### Multi-Tenant Data Flow
1. **Sportsbook Operator Registration**: New operators register via public form
2. **User Association**: Users sign up and are automatically associated with the operator based on subdomain
3. **Data Isolation**: All user data (bets, transactions, etc.) is filtered by sportsbook_operator_id
4. **Revenue Tracking**: Each operator's revenue is tracked separately

### Super Admin Access
- Super admins can view all data across all operators
- Global analytics aggregate data from all operators
- Individual operator performance can be analyzed
- Operators can be enabled/disabled by super admins

## Security Considerations

### Data Isolation
- All queries in tenant-specific areas MUST include sportsbook_operator_id filter
- Middleware will automatically inject operator context based on subdomain
- No cross-tenant data leakage allowed

### Authentication Levels
1. **Regular Users**: Access only their own data within their operator's scope
2. **Sportsbook Operators**: Access all data for their specific sportsbook
3. **Super Admins**: Access all data across all sportsbooks

## URL Structure

### Public Registration
- `/register-sportsbook` - Public registration form

### Tenant-Specific URLs
- `/sportsbook/<operator_subdomain>` - Customer betting interface
- `/admin/<operator_subdomain>` - Operator admin panel

### Super Admin URLs
- `/superadmin` - Super admin login
- `/superadmin/dashboard` - Global dashboard
- `/superadmin/operators` - Manage operators
- `/superadmin/analytics` - Global analytics

## Migration Strategy

1. Create new tables (sportsbook_operators, super_admins)
2. Add foreign key columns to existing tables
3. Create default super admin account
4. Update all existing data to associate with a default operator
5. Update application code to support multi-tenancy
6. Test data isolation thoroughly

## Default Data

### Default Super Admin
```sql
INSERT INTO super_admins (username, password_hash, email, permissions) 
VALUES ('superadmin', '<hashed_password>', 'admin@goalserve.com', '{"all": true}');
```

### Default Sportsbook Operator (for existing data)
```sql
INSERT INTO sportsbook_operators (sportsbook_name, login, password_hash, subdomain, email) 
VALUES ('Default Sportsbook', 'admin', '<hashed_password>', 'default', 'admin@default.com');
```


# GoalServe Sports Betting Platform - System Flow Documentation

## 🎯 Overview

This document provides a complete mapping of the system's URL structure, user flows, authentication, and API expectations. It serves as the foundation for auditing and fixing any broken redirects or misaligned flows.

## 🏗️ System Architecture

- **Frontend**: HTML/JS/CSS served from Flask static files
- **Backend**: Flask API endpoints with SQLite database
- **Multi-tenancy**: Each sportsbook operator gets their own subdomain
- **Authentication**: JWT tokens for API calls, Flask sessions for admin interfaces

## 📍 URL Structure & Flow Mapping

### 1. Sportsbook Registration Flow

#### Entry Point
- **URL**: `/register-sportsbook`
- **File**: `src/static/register-sportsbook.html`
- **Purpose**: New sportsbook operators register their business

#### Registration Process
1. **Form Submission**: POST to `/api/register-sportsbook`
2. **Backend Processing**: Creates operator account + 4 wallets
3. **Success Response**: Returns operator details including subdomain
4. **Frontend Redirect**: JavaScript redirects to admin login

#### Expected API Response
```json
{
  "success": true,
  "message": "Sportsbook registered successfully",
  "data": {
    "operator_id": 123,
    "subdomain": "demosportshub",
    "sportsbook_name": "Demo Sports Hub",
    "login": "admin",
    "email": "admin@demosportshub.com"
  }
}
```

#### Post-Registration Flow
- **Frontend Action**: `window.location.href = '/admin-login?sb=demosportshub'`
- **Target**: Admin login page with sportsbook context

---

### 2. Admin Authentication Flow

#### Admin Login Page
- **URL**: `/admin-login?sb=<subdomain>`
- **File**: `src/static/admin-login.html`
- **Purpose**: Sportsbook operator login

#### Login Process
1. **Form Submission**: POST to `/api/admin-login`
2. **Backend Validation**: Checks operator credentials
3. **Success Response**: Returns JWT token + operator info
4. **Frontend Redirect**: JavaScript redirects to admin dashboard

#### Expected API Response
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "token": "jwt_token_here",
    "operator": {
      "id": 123,
      "sportsbook_name": "Demo Sports Hub",
      "subdomain": "demosportshub",
      "email": "admin@demosportshub.com"
    }
  }
}
```

#### Post-Login Flow
- **Frontend Action**: `window.location.href = '/demosportshub/admin'`
- **Target**: Sportsbook-specific admin dashboard

---

### 3. Superadmin Authentication Flow

#### Superadmin Login Page
- **URL**: `/superadmin`
- **File**: Rendered by Flask route (no static file)
- **Purpose**: Global platform administration

#### Login Process
1. **Form Submission**: POST to `/api/superadmin/login`
2. **Backend Validation**: Checks superadmin credentials
3. **Success Response**: Sets Flask session
4. **Frontend Redirect**: Redirects to superadmin dashboard

#### Expected API Response
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "superadmin_id": 1,
    "username": "superadmin",
    "email": "admin@goalserve.com"
  }
}
```

#### Post-Login Flow
- **Backend Action**: `redirect('/superadmin/rich-dashboard')`
- **Target**: Superadmin dashboard

---

### 4. Customer Betting Interface Flow

#### Sportsbook Home Page
- **URL**: `/<subdomain>` (e.g., `/demosportshub`)
- **File**: `src/static/index.html` (dynamically branded)
- **Purpose**: Customer betting interface

#### Authentication Check
1. **Frontend Check**: JavaScript checks localStorage for JWT token
2. **Token Validation**: API call to `/api/auth/<subdomain>/profile`
3. **Unauthenticated**: Redirects to `/<subdomain>/login`
4. **Authenticated**: Loads betting interface

#### Expected API Response (Profile)
```json
{
  "success": true,
  "data": {
    "user": {
      "id": 456,
      "username": "customer123",
      "email": "customer@example.com",
      "balance": 1000.00,
      "operator_id": 123
    }
  }
}
```

---

### 5. Customer Authentication Flow

#### Customer Login Page
- **URL**: `/<subdomain>/login` (e.g., `/demosportshub/login`)
- **File**: Rendered by Flask route with operator branding
- **Purpose**: Customer login/registration

#### Login Process
1. **Form Submission**: POST to `/api/auth/<subdomain>/login`
2. **Backend Validation**: Checks customer credentials
3. **Success Response**: Returns JWT token
4. **Frontend Redirect**: JavaScript redirects to sportsbook home

#### Expected API Response
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "token": "jwt_token_here",
    "user": {
      "id": 456,
      "username": "customer123",
      "email": "customer@example.com"
    }
  }
}
```

#### Post-Login Flow
- **Frontend Action**: `window.location.href = '/demosportshub'`
- **Target**: Sportsbook betting interface

---

## 🔐 Authentication & Authorization

### JWT Token Structure
```json
{
  "user_id": 456,
  "operator_id": 123,
  "username": "customer123",
  "exp": 1640995200,
  "iat": 1640908800
}
```

### Protected Routes
- **Customer Routes**: Require valid JWT token
- **Admin Routes**: Require valid JWT token + operator context
- **Superadmin Routes**: Require Flask session

### Token Validation
- **Header**: `Authorization: Bearer <token>`
- **Validation**: `/api/auth/<subdomain>/profile` endpoint
- **Expiry**: 24 hours (configurable)

---

## 🎨 Multi-Tenant Branding

### Theme Customization
- **URL**: `/api/theme-css/<subdomain>`
- **Purpose**: Dynamic CSS generation per operator
- **Features**: Colors, fonts, logos, sportsbook names

### Branding Injection
- **CSS Variables**: Applied to document root
- **Logo Updates**: Dynamic logo text and icons
- **Color Schemes**: Primary, secondary, accent colors

---

## 🎮 Games & Betting Interface

### Games Page
- **URL**: `/<subdomain>/games`
- **Access**: Requires customer authentication
- **Purpose**: Display available sports and matches

### Betting Process
1. **Match Selection**: Customer selects sporting event
2. **Odds Display**: Real-time odds from GoalServe API
3. **Bet Placement**: POST to `/api/betting/place-bet`
4. **Confirmation**: Bet slip confirmation

---

## 🔄 Redirect Flow Summary

### Registration → Admin Login
```
/register-sportsbook → /admin-login?sb=<subdomain>
```

### Admin Login → Admin Dashboard
```
/admin-login?sb=<subdomain> → /<subdomain>/admin
```

### Superadmin Login → Superadmin Dashboard
```
/superadmin → /superadmin/rich-dashboard
```

### Customer Login → Betting Interface
```
/<subdomain>/login → /<subdomain>
```

### Unauthenticated Access → Login
```
/<subdomain> → /<subdomain>/login (if no token)
```

---

## 🚨 Common Issues & Fixes

### 1. Broken Redirects
- **Issue**: Frontend JavaScript redirects to wrong URLs
- **Fix**: Ensure all redirects use correct subdomain context

### 2. API Endpoint Mismatches
- **Issue**: Frontend calls wrong API endpoints
- **Fix**: Verify all API calls include correct subdomain

### 3. Authentication Context Loss
- **Issue**: Users lose operator context during navigation
- **Fix**: Maintain subdomain in all authentication flows

### 4. Theme Loading Failures
- **Issue**: Branding not applied correctly
- **Fix**: Ensure theme API endpoints return correct data

---

## 📋 API Endpoint Reference

### Authentication Endpoints
- `POST /api/register-sportsbook` - Sportsbook registration
- `POST /api/admin-login` - Admin authentication
- `POST /api/superadmin/login` - Superadmin authentication
- `POST /api/auth/<subdomain>/login` - Customer authentication
- `GET /api/auth/<subdomain>/profile` - User profile validation

### Admin Endpoints
- `GET /<subdomain>/admin` - Admin dashboard
- `GET /superadmin/rich-dashboard` - Superadmin dashboard

### Theme Endpoints
- `GET /api/theme-css/<subdomain>` - Dynamic CSS generation
- `GET /<subdomain>/api/public/load-theme` - Theme data loading

### Betting Endpoints
- `GET /<subdomain>/games` - Games display
- `POST /api/betting/place-bet` - Bet placement

---

## 🔍 Audit Checklist

### Frontend JavaScript
- [ ] All redirects use correct subdomain context
- [ ] API calls include proper authentication headers
- [ ] Error handling for failed API responses
- [ ] Theme loading and application logic

### Backend Routes
- [ ] All routes properly handle subdomain context
- [ ] Authentication decorators applied correctly
- [ ] API responses match frontend expectations
- [ ] Error handling and status codes

### Database Queries
- [ ] Multi-tenant data isolation
- [ ] Proper foreign key relationships
- [ ] Index optimization for performance

### Security
- [ ] JWT token validation
- [ ] Session management
- [ ] CORS configuration
- [ ] Input validation and sanitization

---

This document provides the complete foundation for auditing and fixing the GoalServe Sports Betting Platform. Use it to identify broken flows, misaligned redirects, and API inconsistencies.

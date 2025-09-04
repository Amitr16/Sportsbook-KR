# 🚀 Quick Deployment Reference

## 📋 Prerequisites
- [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- [Cloudflare account](https://dash.cloudflare.com/sign-up)
- Git installed

## ⚡ Quick Start (Windows PowerShell)

### 1. Install Fly.io CLI
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### 2. Login to Fly.io
```powershell
fly auth login
```

### 3. Run Automated Deployment
```powershell
.\deploy.ps1
```

## ⚡ Quick Start (macOS/Linux)

### 1. Install Fly.io CLI
```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Login to Fly.io
```bash
fly auth login
```

### 3. Run Automated Deployment
```bash
chmod +x deploy.sh
./deploy.sh
```

## 🔧 Manual Deployment Steps

### Backend (Fly.io)
```bash
# Create app
fly apps create goalserve-sportsbook-backend

# Create PostgreSQL
fly postgres create goalserve-postgres

# Attach database
fly postgres attach goalserve-postgres --app goalserve-sportsbook-backend

# Set secrets
fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
fly secrets set JWT_SECRET_KEY="$(openssl rand -hex 32)"
fly secrets set FLASK_ENV="production"
fly secrets set FLASK_DEBUG="false"

# Deploy
fly deploy
```

### Frontend (Cloudflare Pages)
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Pages → Create a project
3. Connect GitHub repository
4. Build settings:
   - Build command: `echo "Static build"`
   - Build output directory: `src/static`
5. Deploy

## 🌐 Final URLs
- **Backend**: `https://goalserve-sportsbook-backend.fly.dev`
- **Frontend**: `https://goalserve-sportsbook-frontend.pages.dev`

## 🔍 Test Deployment
```bash
# Health check
curl https://goalserve-sportsbook-backend.fly.dev/health

# Check logs
fly logs
```

## 📖 Full Guide
See `DEPLOYMENT_GUIDE.md` for complete instructions.

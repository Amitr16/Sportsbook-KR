# 🚀 Complete Deployment Guide: Fly.io (Backend) + Cloudflare Pages (Frontend)

This guide will walk you through deploying the GoalServe Sports Betting Platform to production using Fly.io for the backend and Cloudflare Pages for the frontend.

## 📋 Prerequisites

- [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- [Cloudflare account](https://dash.cloudflare.com/sign-up) 
- [Git](https://git-scm.com/) installed
- PostgreSQL database (we'll use Fly.io's managed PostgreSQL)

## 🔧 Step 1: Prepare Your Project

### 1.1 Install Fly.io CLI
```bash
# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

# macOS/Linux
curl -L https://fly.io/install.sh | sh
```

### 1.2 Login to Fly.io
```bash
fly auth login
```

### 1.3 Verify your project structure
Your project should have these deployment files:
- `fly.toml` - Fly.io configuration
- `Dockerfile` - Container configuration
- `.dockerignore` - Docker build exclusions
- `env.production` - Production environment template

## 🗄️ Step 2: Set Up PostgreSQL Database

### 2.1 Create PostgreSQL app on Fly.io
```bash
fly postgres create goalserve-postgres
```

### 2.2 Attach PostgreSQL to your app
```bash
fly postgres attach goalserve-postgres --app goalserve-sportsbook-backend
```

### 2.3 Get database connection details
```bash
fly postgres show goalserve-postgres
```

## 🌐 Step 3: Deploy Backend to Fly.io

### 3.1 Create the app
```bash
fly apps create goalserve-sportsbook-backend
```

### 3.2 Set up secrets (environment variables)
```bash
# Generate secure secret keys
fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
fly secrets set JWT_SECRET_KEY="$(openssl rand -hex 32)"

# Set database URL (replace with your actual database URL)
fly secrets set DATABASE_URL="postgresql://postgres:password@goalserve-postgres.internal:5432/goalserve_sportsbook"

# Set other environment variables
fly secrets set FLASK_ENV="production"
fly secrets set FLASK_DEBUG="false"
fly secrets set HOST="0.0.0.0"
fly secrets set PORT="8080"

# Set your actual API keys and OAuth credentials
fly secrets set GOOGLE_CLIENT_ID="your-google-oauth-client-id"
fly secrets set GOOGLE_CLIENT_SECRET="your-google-oauth-client-secret"
fly secrets set GOALSERVE_API_KEY="your-goalserve-api-key"
```

### 3.3 Create volume for persistent data
```bash
fly volumes create goalserve_data --size 10 --region iad
```

### 3.4 Deploy the application
```bash
fly deploy
```

### 3.5 Verify deployment
```bash
fly status
fly logs
```

### 3.6 Test the health endpoint
```bash
curl https://goalserve-sportsbook-backend.fly.dev/health
```

## 🎨 Step 4: Deploy Frontend to Cloudflare Pages

### 4.1 Prepare frontend files
The frontend is already in the `src/static/` directory. We'll deploy this to Cloudflare Pages.

### 4.2 Install Wrangler CLI
```bash
npm install -g wrangler
```

### 4.3 Login to Cloudflare
```bash
wrangler login
```

### 4.4 Deploy to Cloudflare Pages
```bash
# Navigate to frontend directory
cd frontend

# Deploy to Cloudflare Pages
wrangler pages deploy src/static --project-name goalserve-sportsbook-frontend
```

### 4.5 Alternative: Manual Cloudflare Pages Deployment
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to Pages → Create a project
3. Connect your GitHub repository
4. Set build settings:
   - Build command: `echo "Static build"`
   - Build output directory: `src/static`
   - Root directory: `/`
5. Deploy

## 🔗 Step 5: Configure CORS and Frontend-Backend Communication

### 5.1 Update CORS origins in Fly.io
```bash
# Get your Cloudflare Pages URL
fly secrets set CORS_ORIGINS="https://goalserve-sportsbook-frontend.pages.dev,https://your-custom-domain.com"
```

### 5.2 Update frontend API endpoints
In your frontend HTML files, update API calls to point to your Fly.io backend:

```javascript
// Replace localhost:5000 with your Fly.io URL
const API_BASE_URL = 'https://goalserve-sportsbook-backend.fly.dev';
```

### 5.2 Redeploy backend with updated CORS
```bash
fly deploy
```

## 🌍 Step 6: Custom Domain Setup (Optional)

### 6.1 Add custom domain to Fly.io backend
```bash
fly certs add your-domain.com
```

### 6.2 Add custom domain to Cloudflare Pages
1. Go to Cloudflare Pages project
2. Navigate to Custom domains
3. Add your domain
4. Update DNS records as instructed

## 🔍 Step 7: Testing and Verification

### 7.1 Test backend endpoints
```bash
# Health check
curl https://goalserve-sportsbook-backend.fly.dev/health

# Test sports API
curl https://goalserve-sportsbook-backend.fly.dev/api/sports/soccer
```

### 7.2 Test frontend
- Visit your Cloudflare Pages URL
- Test user registration and login
- Test betting functionality
- Verify WebSocket connections

### 7.3 Monitor logs
```bash
# Backend logs
fly logs

# Database logs
fly postgres logs goalserve-postgres
```

## 🚨 Step 8: Production Security Checklist

### 8.1 Environment Variables
- [ ] All sensitive data moved to Fly.io secrets
- [ ] No hardcoded credentials in code
- [ ] Production database URL configured

### 8.2 Security Headers
- [ ] HTTPS enforced
- [ ] CORS properly configured
- [ ] Rate limiting implemented (if needed)

### 8.3 Monitoring
- [ ] Health checks working
- [ ] Logs accessible
- [ ] Error tracking configured

## 🔄 Step 9: Continuous Deployment

### 9.1 Set up GitHub Actions (Optional)
Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Fly.io
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
```

### 9.2 Automatic deployments
```bash
# Enable automatic deployments
fly autoscale set min=1 max=3
```

## 📊 Step 10: Performance Optimization

### 10.1 Database optimization
```bash
# Monitor database performance
fly postgres connect goalserve-postgres
```

### 10.2 Application scaling
```bash
# Scale based on demand
fly scale count 2
fly scale memory 2048
```

## 🆘 Troubleshooting

### Common Issues:

1. **Database Connection Failed**
   ```bash
   fly postgres connect goalserve-postgres
   fly logs
   ```

2. **Build Failed**
   ```bash
   fly logs
   fly deploy --remote-only
   ```

3. **CORS Issues**
   - Verify CORS_ORIGINS secret is set correctly
   - Check frontend is calling correct backend URL
   - Redeploy backend after CORS changes

4. **Static Files Not Loading**
   - Verify static folder path in Dockerfile
   - Check file permissions
   - Verify .dockerignore exclusions

## 📞 Support

- **Fly.io**: [Documentation](https://fly.io/docs/) | [Community](https://community.fly.io/)
- **Cloudflare Pages**: [Documentation](https://developers.cloudflare.com/pages/)
- **Project Issues**: Check the project repository

## 🎯 Final URLs

After deployment, you'll have:
- **Backend**: `https://goalserve-sportsbook-backend.fly.dev`
- **Frontend**: `https://goalserve-sportsbook-frontend.pages.dev`
- **Database**: Managed PostgreSQL on Fly.io

## 🚀 Next Steps

1. Set up monitoring and alerting
2. Configure backup strategies
3. Set up staging environment
4. Implement CI/CD pipeline
5. Add performance monitoring
6. Set up SSL certificates for custom domains

---

**🎉 Congratulations! Your GoalServe Sports Betting Platform is now deployed to production!**


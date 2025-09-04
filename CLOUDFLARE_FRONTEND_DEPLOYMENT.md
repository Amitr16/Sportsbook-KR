# Cloudflare Frontend Deployment Guide

## 🚀 Quick Deployment (Minimal Setup)

Your frontend is already configured for Cloudflare Pages deployment! Here's how to deploy with minimal setup:

### Prerequisites
- Node.js installed
- Cloudflare account
- Your frontend files are in `src/static/`

### Option 1: One-Command Deployment (Recommended)

**For Windows (PowerShell):**
```powershell
cd frontend
.\deploy_cloudflare.ps1
```

**For Linux/Mac:**
```bash
cd frontend
chmod +x deploy_cloudflare.sh
./deploy_cloudflare.sh
```

### Option 2: Manual Deployment

1. **Install Wrangler CLI:**
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare:**
   ```bash
   wrangler login
   ```

3. **Deploy to Cloudflare Pages:**
   ```bash
   wrangler pages deploy ../src/static --project-name=goalserve-sportsbook-frontend
   ```

### Option 3: Git Integration (Automatic Deployments)

1. **Connect your GitHub repository to Cloudflare Pages:**
   - Go to Cloudflare Dashboard → Pages
   - Click "Create a project"
   - Connect your GitHub repository
   - Set build settings:
     - **Build command:** `echo 'Static site - no build required'`
     - **Build output directory:** `src/static`
     - **Root directory:** `/`

2. **Automatic deployments:**
   - Every push to `main` branch will trigger automatic deployment
   - Preview deployments for pull requests

## 🌐 Your Frontend URL

After deployment, your frontend will be available at:
- **Production:** `https://goalserve-sportsbook-frontend.pages.dev`
- **Custom domain:** You can add your own domain in Cloudflare Pages settings

## 📁 Project Structure

```
frontend/
├── deploy_cloudflare.ps1    # Windows deployment script
├── deploy_cloudflare.sh     # Linux/Mac deployment script
├── package.json             # Project configuration
├── wrangler.toml           # Cloudflare configuration
└── ../src/static/          # Your frontend files
    ├── index.html
    ├── login.html
    ├── admin-dashboard.html
    └── ... (other HTML files)
```

## ⚙️ Configuration Details

### wrangler.toml
- **Project name:** `goalserve-sportsbook-frontend`
- **Static files location:** `../src/static`
- **No build process required** (static HTML files)
- **Production branch:** `main`

### Features Included
- ✅ Static HTML deployment
- ✅ Custom domain support
- ✅ SSL/HTTPS automatically enabled
- ✅ Global CDN
- ✅ Automatic deployments (if using Git integration)
- ✅ Preview deployments for testing

## 🔧 Customization

### Adding Custom Domain
1. Go to Cloudflare Pages dashboard
2. Select your project
3. Go to "Custom domains"
4. Add your domain
5. Update DNS records as instructed

### Environment Variables
If you need environment variables for your frontend:
1. Go to Pages dashboard → Settings → Environment variables
2. Add your variables for Production/Preview environments

### Build Settings
Since you're using static HTML files, no build process is needed. If you want to add a build step later:
1. Update `wrangler.toml` build command
2. Add build dependencies to `package.json`

## 🚨 Troubleshooting

### Common Issues

1. **"Wrangler not found"**
   ```bash
   npm install -g wrangler
   ```

2. **Authentication failed**
   ```bash
   wrangler logout
   wrangler login
   ```

3. **Deployment failed**
   - Check that `src/static/` directory exists
   - Verify all HTML files are valid
   - Check Cloudflare Pages dashboard for error logs

### Getting Help
- Cloudflare Pages documentation: https://developers.cloudflare.com/pages/
- Wrangler CLI docs: https://developers.cloudflare.com/workers/wrangler/

## 🎯 Next Steps

1. **Deploy your frontend** using one of the methods above
2. **Test your deployment** at the provided URL
3. **Add custom domain** if needed
4. **Set up automatic deployments** via Git integration
5. **Configure environment variables** if your frontend needs them

Your frontend will be live and accessible worldwide with Cloudflare's global CDN! 🌍

# 🚀 Frontend Deployment to Cloudflare Pages

## 📋 Prerequisites

1. **Cloudflare Account**: Sign up at [cloudflare.com](https://cloudflare.com)
2. **Git Repository**: Your project should be in a Git repository
3. **Backend Running**: Your Fly.io backend should be working (✅ Already done!)

## 🛠️ Step-by-Step Deployment

### **Step 1: Build Your Frontend**

#### **On Windows (PowerShell):**
```powershell
cd frontend
.\build.ps1
```

#### **On macOS/Linux:**
```bash
cd frontend
chmod +x build.sh
./build.sh
```

### **Step 2: Deploy to Cloudflare Pages**

#### **Option A: Using Cloudflare Dashboard (Recommended)**

1. **Go to Cloudflare Dashboard**
   - Visit [dash.cloudflare.com](https://dash.cloudflare.com)
   - Click "Pages" in the sidebar

2. **Create New Project**
   - Click "Create a project"
   - Choose "Connect to Git"

3. **Connect Your Repository**
   - Select your Git provider (GitHub, GitLab, etc.)
   - Choose your repository
   - Click "Install and authorize"

4. **Configure Build Settings**
   - **Project name**: `goalserve-sportsbook-frontend`
   - **Production branch**: `main` or `master`
   - **Build command**: `npm run build` (or leave empty for static files)
   - **Build output directory**: `build`
   - **Root directory**: `frontend`

5. **Environment Variables**
   - Add `BACKEND_URL` = `https://goalserve-sportsbook-backend.fly.dev`

6. **Deploy**
   - Click "Save and Deploy"

#### **Option B: Using Wrangler CLI**

1. **Install Wrangler:**
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare:**
   ```bash
   wrangler login
   ```

3. **Deploy:**
   ```bash
   cd frontend
   wrangler pages deploy build --project-name goalserve-sportsbook-frontend
   ```

## 🔧 Configuration

### **Backend URL Configuration**

Your frontend needs to know where your backend is. Update your HTML files to use the production backend URL:

```javascript
// Replace localhost:5000 with your Fly.io backend
const BACKEND_URL = 'https://goalserve-sportsbook-backend.fly.dev';
```

### **CORS Configuration**

Your backend already has CORS configured, but make sure it includes your Cloudflare Pages domain.

## 🌐 After Deployment

### **Your Frontend Will Be Available At:**
```
https://goalserve-sportsbook-frontend.pages.dev
```

### **Custom Domain (Optional):**
1. Go to your Cloudflare Pages project
2. Click "Custom domains"
3. Add your domain (e.g., `app.yourdomain.com`)

## 🧪 Testing

### **Test Your Complete Application:**
1. **Frontend**: Visit your Cloudflare Pages URL
2. **Backend**: Test API endpoints
3. **Integration**: Ensure frontend can communicate with backend

## 🔍 Troubleshooting

### **Common Issues:**

1. **Build Failures**
   - Check build output directory path
   - Ensure all static files are copied

2. **CORS Errors**
   - Verify backend CORS configuration
   - Check backend URL in frontend code

3. **404 Errors**
   - Ensure `index.html` is in the build directory
   - Check Cloudflare Pages build settings

## 🎯 Next Steps

1. **Test Complete Application**
2. **Set Up Custom Domain** (optional)
3. **Configure Analytics** (optional)
4. **Set Up Monitoring** (optional)

## 📞 Support

- **Cloudflare Pages Docs**: [developers.cloudflare.com/pages](https://developers.cloudflare.com/pages)
- **Cloudflare Community**: [community.cloudflare.com](https://community.cloudflare.com)

---

**🎉 Congratulations! You'll have a complete, production-ready application with:**
- **Backend**: Fly.io (✅ Already deployed!)
- **Frontend**: Cloudflare Pages
- **Database**: Fly.io managed PostgreSQL
- **Global CDN**: Cloudflare's worldwide network

# Google OAuth Setup Guide

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API (or Google Identity API)
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Choose "Web application"
6. Add these redirect URIs:
   - For local development: `http://localhost:5000/auth/google/callback`
   - For production: `https://your-app-name.fly.dev/auth/google/callback`

## Step 2: Update Environment Variables

### Local Development (`env.local`):
```bash
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### Production (`env.production`):
```bash
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
GOOGLE_REDIRECT_URI=https://your-app-name.fly.dev/auth/google/callback
```

## Step 3: Test the Setup

1. Start your local server: `python run.py`
2. Visit: `http://localhost:5000/megabook`
3. Click "Sign in with Google"
4. Complete Google OAuth flow
5. You should be redirected back and logged in

## How It Works

1. **User clicks "Sign in with Google"** → Redirects to Google OAuth
2. **User authorizes on Google** → Google redirects back with authorization code
3. **Backend exchanges code for tokens** → Gets user info from Google
4. **Backend checks database**:
   - If user exists → Updates last_login
   - If new user → Creates new user with $1000 balance
5. **Backend sets session** → User is logged in
6. **User redirected back** → Full betting functionality enabled

## Troubleshooting

- **"Sign in with Google" not working**: Check if GOOGLE_CLIENT_ID is set
- **Redirect URI mismatch**: Ensure redirect URI in Google Console matches your environment
- **User not created**: Check database connection and logs
- **Session not persisting**: Check SECRET_KEY is set

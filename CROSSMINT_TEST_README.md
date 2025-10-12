# Crossmint API Credentials Test

This test script verifies if your Crossmint API credentials are valid and have the correct permissions.

## Prerequisites

1. **Python 3.7+** installed
2. **pip** package manager
3. **Crossmint Account** with API credentials

## Setup

### 1. Install Required Packages

```bash
pip install requests python-dotenv
```

Or if using requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. Get Your Crossmint Credentials

1. Go to https://console.crossmint.com
2. Sign in or create an account
3. Create a new project (or use existing one)
4. Navigate to **"API Keys"** section
5. Create a **Server-Side API Key** with these permissions:
   - ✅ `wallets.create`
   - ✅ `wallets.read`
   - ✅ `wallets.transfer`
6. Copy the following:
   - **API Key** (starts with `sk_staging_...` or `sk_production_...`)
   - **Project ID** (UUID format like `de2abfe2-ca98-4335-9b47-939a2f6dda25`)

## Running the Test

### Option 1: Interactive Mode (Recommended)

Simply run the script and enter credentials when prompted:

```bash
python test_crossmint_credentials.py
```

The script will ask you to enter:
- `CROSSMINT_API_KEY`
- `CROSSMINT_PROJECT_ID`
- `CROSSMINT_ENVIRONMENT` (staging or production)

### Option 2: Using Environment Variables

Set environment variables first:

**Windows (PowerShell):**
```powershell
$env:CROSSMINT_API_KEY="sk_staging_YOUR_API_KEY_HERE"
$env:CROSSMINT_PROJECT_ID="YOUR_PROJECT_ID_HERE"
$env:CROSSMINT_ENVIRONMENT="staging"
python test_crossmint_credentials.py
```

**Windows (Command Prompt):**
```cmd
set CROSSMINT_API_KEY=sk_staging_YOUR_API_KEY_HERE
set CROSSMINT_PROJECT_ID=YOUR_PROJECT_ID_HERE
set CROSSMINT_ENVIRONMENT=staging
python test_crossmint_credentials.py
```

**Linux/Mac:**
```bash
export CROSSMINT_API_KEY="sk_staging_YOUR_API_KEY_HERE"
export CROSSMINT_PROJECT_ID="YOUR_PROJECT_ID_HERE"
export CROSSMINT_ENVIRONMENT="staging"
python test_crossmint_credentials.py
```

### Option 3: Using .env File

Create a `.env` file in the same directory:

```bash
CROSSMINT_API_KEY=sk_staging_YOUR_API_KEY_HERE
CROSSMINT_PROJECT_ID=YOUR_PROJECT_ID_HERE
CROSSMINT_ENVIRONMENT=staging
```

Then run:

```bash
python test_crossmint_credentials.py
```

## Expected Results

### ✅ Success (Status Code 201)

If your credentials are valid and have the correct permissions, you'll see:

```
🎉 SUCCESS! Wallet created successfully!
================================================================================
✅ Wallet Address: 0x1234...abcd
✅ Wallet ID: cm_wallet_123...
✅ Chain: aptos

✅ Your Crossmint credentials are VALID and have the correct permissions!
```

### ❌ Error 403 (Forbidden)

If you see this error:

```
❌ AUTHENTICATION ERROR (403 Forbidden)
================================================================================

Possible causes:
1. ❌ API key is invalid or expired
2. ❌ API key doesn't have 'wallets.create' permission
3. ❌ Project ID doesn't match the API key
```

**How to fix:**

1. Go to https://console.crossmint.com
2. Navigate to **"API Keys"** section
3. Check if your API key has these scopes enabled:
   - `wallets.create`
   - `wallets.read`
   - `wallets.transfer`
4. If scopes are missing, **edit the API key** and enable them
5. OR **create a new API key** with all wallet permissions enabled
6. Update your credentials and run the test again

### ❌ Error 400 (Bad Request)

The request format is incorrect. This usually means the API endpoint or payload structure has changed. Contact support.

## What This Test Does

1. **Loads your Crossmint credentials** (API key, Project ID, Environment)
2. **Configures the Crossmint API client** with proper headers
3. **Attempts to create a test Aptos wallet** using the `/v1-alpha2/wallets` endpoint
4. **Verifies the response** and reports success or failure

## Troubleshooting

### "API key is required"
- Make sure you've entered the API key when prompted
- OR set the `CROSSMINT_API_KEY` environment variable
- The API key should start with `sk_staging_` or `sk_production_`

### "Project ID is required"
- Make sure you've entered the Project ID when prompted
- OR set the `CROSSMINT_PROJECT_ID` environment variable
- The Project ID is a UUID (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### "403 Forbidden" persists after enabling permissions
- Wait 1-2 minutes for permission changes to propagate
- Try creating a **brand new API key** instead of editing the old one
- Ensure you're using the **Server-Side API Key**, not the Client-Side key

### "Request Timeout"
- Check your internet connection
- Try again in a few minutes
- Crossmint staging/production servers might be experiencing issues

## Next Steps

Once the test passes (✅ SUCCESS), you can use these credentials in your application:

1. Update your `postgresql.env` or `.env` file:
   ```bash
   CROSSMINT_API_KEY=sk_staging_YOUR_WORKING_KEY
   CROSSMINT_PROJECT_ID=YOUR_WORKING_PROJECT_ID
   CROSSMINT_ENVIRONMENT=staging
   ```

2. Restart your Flask application to load the new credentials

3. Test operator registration - Web3 wallets should now be created successfully!

## Support

- **Crossmint Documentation**: https://docs.crossmint.com
- **Crossmint Console**: https://console.crossmint.com
- **Crossmint Support**: support@crossmint.com

## API Endpoints Used

- **Staging**: `https://staging.crossmint.com/api/v1-alpha2/wallets`
- **Production**: `https://www.crossmint.com/api/v1-alpha2/wallets`

## Required Headers

```
X-API-KEY: <your-server-side-api-key>
X-PROJECT-ID: <your-project-id>
Content-Type: application/json
```

## Test Wallet Payload

```json
{
  "type": "aptos-mpc-wallet",
  "linkedUser": "email:test_user@example.com",
  "metadata": {
    "user_id": 9999,
    "email": "test_user@example.com",
    "username": "testuser",
    "operator_id": 9999,
    "wallet_type": "test",
    "created_at": "2025-10-11T17:00:00.000000"
  }
}
```

---

**Good luck!** 🚀


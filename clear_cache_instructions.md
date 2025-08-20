# Browser Cache Clearing Instructions

The disabled event filtering is working correctly on the backend, but you may be seeing cached data in your browser. Here's how to clear the cache:

## Method 1: Hard Refresh (Recommended)
1. **Chrome/Edge**: Press `Ctrl + Shift + R` or `Ctrl + F5`
2. **Firefox**: Press `Ctrl + Shift + R` or `Ctrl + F5`
3. **Safari**: Press `Cmd + Option + R`

## Method 2: Clear Browser Cache
1. **Chrome/Edge**:
   - Press `F12` to open Developer Tools
   - Right-click the refresh button
   - Select "Empty Cache and Hard Reload"

2. **Firefox**:
   - Press `F12` to open Developer Tools
   - Click the gear icon (Settings)
   - Check "Disable Cache (when toolbox is open)"
   - Refresh the page

## Method 3: Incognito/Private Mode
1. Open a new incognito/private window
2. Navigate to `http://localhost:5000`
3. Check if the disabled event is still visible

## Method 4: Clear All Browser Data
1. **Chrome/Edge**: `Ctrl + Shift + Delete`
2. **Firefox**: `Ctrl + Shift + Delete`
3. Select "Cached images and files"
4. Click "Clear data"

## Verification
After clearing cache, the event "Tagawa vs SBA" (ID: 975970) should no longer appear in the user interface, or if it does appear, the "Home/Away" market (market ID: 2) should be missing.

The backend filtering is working correctly - the API is not returning the disabled market.

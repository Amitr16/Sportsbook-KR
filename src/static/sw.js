/**
 * Service Worker for pre-caching odds data
 * Enables instant odds loading after login
 */

const CACHE_NAME = 'odds-prewarm-v1';
const PUBLIC_SNAPSHOT = '/api/public/snapshot';

self.addEventListener('install', (evt) => {
  console.log('🔧 Service Worker installing...');
  self.skipWaiting();
});

self.addEventListener('activate', (evt) => {
  console.log('✅ Service Worker activated');
  evt.waitUntil(self.clients.claim());
});

async function cachePut(url, resp) {
  try {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(url, resp.clone());
    console.log('💾 Cached response for:', url);
  } catch (error) {
    console.error('❌ Error caching response:', error);
  }
}

self.addEventListener('message', (evt) => {
  console.log('📨 Service Worker received message:', evt.data);
  
  if (evt.data === 'prefetch:public-snapshot') {
    console.log('🚀 Starting snapshot prefetch...');
    
    evt.waitUntil(
      fetch(PUBLIC_SNAPSHOT, { 
        cache: 'no-cache',
        headers: {
          'Accept': 'application/json'
        }
      })
        .then(response => {
          if (response.ok) {
            console.log('✅ Snapshot prefetch successful');
            return cachePut(PUBLIC_SNAPSHOT, response);
          } else {
            console.warn('⚠️ Snapshot prefetch failed:', response.status);
          }
        })
        .catch(error => {
          console.error('❌ Snapshot prefetch error:', error);
        })
    );
  }
});

// Cache-first strategy for public snapshot
self.addEventListener('fetch', (evt) => {
  const url = new URL(evt.request.url);
  
  if (url.pathname === PUBLIC_SNAPSHOT) {
    console.log('🎯 Intercepting snapshot request');
    
    evt.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        try {
          // Try cache first
          const cached = await cache.match(PUBLIC_SNAPSHOT);
          
          // Start network request
          const networkPromise = fetch(PUBLIC_SNAPSHOT, {
            headers: {
              'Accept': 'application/json'
            }
          }).then(response => {
            if (response.ok) {
              // Update cache with fresh data
              cache.put(PUBLIC_SNAPSHOT, response.clone());
            }
            return response;
          }).catch(error => {
            console.warn('🌐 Network request failed, using cache:', error);
            return cached;
          });
          
          // Return cached if available, otherwise wait for network
          if (cached) {
            console.log('⚡ Serving from cache');
            // Still update cache in background
            networkPromise.catch(() => {}); // Ignore errors for background update
            return cached;
          } else {
            console.log('🌐 Serving from network (no cache)');
            return networkPromise;
          }
        } catch (error) {
          console.error('❌ Cache handling error:', error);
          // Fallback to network request
          return fetch(evt.request);
        }
      })
    );
  }
});

// Clean up old caches
self.addEventListener('activate', (evt) => {
  evt.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName.startsWith('odds-prewarm-')) {
            console.log('🗑️ Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

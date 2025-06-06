const CACHE_DURATION = 60 * 60 * 1000; // 1 hour in milliseconds

class CacheManager {
  constructor() {
    this.cache = new Map();
  }

  set(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      expires: Date.now() + CACHE_DURATION
    });
    console.log(`[Cache] Stored ${key} with ${Array.isArray(data) ? data.length : 'N/A'} items`);
  }

  get(key) {
    const cached = this.cache.get(key);
    
    if (!cached) {
      console.log(`[Cache] Miss for ${key} - not found`);
      return null;
    }

    if (Date.now() > cached.expires) {
      console.log(`[Cache] Miss for ${key} - expired`);
      this.cache.delete(key);
      return null;
    }

    console.log(`[Cache] Hit for ${key}`);
    return cached.data;
  }

  isValid(key) {
    const cached = this.cache.get(key);
    return cached && Date.now() <= cached.expires;
  }

  clear(key = null) {
    if (key) {
      this.cache.delete(key);
      console.log(`[Cache] Cleared ${key}`);
    } else {
      this.cache.clear();
      console.log('[Cache] Cleared all cache');
    }
  }

  getStatus() {
    const status = {};
    for (const [key, value] of this.cache.entries()) {
      status[key] = {
        cached: true,
        expires: new Date(value.expires).toISOString(),
        itemCount: Array.isArray(value.data) ? value.data.length : 'N/A'
      };
    }
    return status;
  }
}

export default new CacheManager();
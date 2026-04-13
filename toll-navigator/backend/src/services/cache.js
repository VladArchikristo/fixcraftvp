/**
 * Cache Service — toll route calculation cache
 *
 * Uses node-cache (in-memory) with Redis-compatible interface.
 * To switch to Redis later: replace this module with ioredis wrapper,
 * keeping the same get/set/del API.
 *
 * TTL: 1 hour (3600 seconds) for route calculations
 *       5 minutes (300 seconds) for available states list
 */

const NodeCache = require('node-cache');

const CACHE_TTL_ROUTE  = 60 * 60;      // 1 hour
const CACHE_TTL_STATES = 60 * 5;       // 5 minutes
const CACHE_CHECK_PERIOD = 60 * 10;    // cleanup check every 10 min

const cache = new NodeCache({
  stdTTL: CACHE_TTL_ROUTE,
  checkperiod: CACHE_CHECK_PERIOD,
  useClones: false,
});

/**
 * Build a deterministic cache key for route calculations.
 * Normalises parameters so "Dallas,TX" and "dallas,tx" hit the same key.
 *
 * @param {string} from       - origin city/state string
 * @param {string} to         - destination city/state string
 * @param {string} truckType  - e.g. "5-axle"
 * @returns {string}
 */
function routeCacheKey(from, to, truckType) {
  const f = from.trim().toLowerCase().replace(/\s+/g, '_');
  const t = to.trim().toLowerCase().replace(/\s+/g, '_');
  const tt = (truckType || '2-axle').trim().toLowerCase();
  return `route:${f}:${t}:${tt}`;
}

/**
 * Get cached value. Returns undefined on miss.
 * @param {string} key
 */
function get(key) {
  return cache.get(key);
}

/**
 * Store value in cache.
 * @param {string} key
 * @param {*} value
 * @param {number} [ttl]  - seconds, defaults to CACHE_TTL_ROUTE
 */
function set(key, value, ttl = CACHE_TTL_ROUTE) {
  cache.set(key, value, ttl);
}

/**
 * Delete a specific key.
 * @param {string} key
 */
function del(key) {
  cache.del(key);
}

/**
 * Return cache stats (hits, misses, keys count).
 */
function stats() {
  const s = cache.getStats();
  return {
    keys: cache.keys().length,
    hits: s.hits,
    misses: s.misses,
    hit_rate: s.hits + s.misses > 0
      ? ((s.hits / (s.hits + s.misses)) * 100).toFixed(1) + '%'
      : 'n/a',
  };
}

module.exports = {
  get,
  set,
  del,
  stats,
  routeCacheKey,
  TTL: {
    ROUTE:  CACHE_TTL_ROUTE,
    STATES: CACHE_TTL_STATES,
  },
};

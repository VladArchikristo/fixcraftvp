/**
 * LoadTracking — in-memory store for live load tracking sessions.
 * Each session is identified by a UUID token.
 * Data is ephemeral (restarts clear all sessions) — suitable for
 * short-lived per-load tracking windows. Upgrade to SQLite if
 * persistence across restarts is ever needed.
 */

const { randomUUID } = require('crypto');

// Map<token, session>
const sessions = new Map();

/**
 * @typedef {Object} TrackingSession
 * @property {string}  token
 * @property {number}  driverId
 * @property {number|null} lat
 * @property {number|null} lng
 * @property {number|null} speed      — mph
 * @property {string}  destination
 * @property {string|null} eta        — ISO string or human label
 * @property {boolean} active
 * @property {string}  createdAt      — ISO
 * @property {string|null} updatedAt  — ISO
 */

const LoadTracking = {
  /**
   * Create a new tracking session.
   * @param {number} driverId
   * @param {string} destination
   * @returns {TrackingSession}
   */
  create(driverId, destination) {
    const token = randomUUID().replace(/-/g, '').toUpperCase().slice(0, 12);
    const session = {
      token,
      driverId,
      lat: null,
      lng: null,
      speed: null,
      destination: destination || '',
      eta: null,
      active: true,
      createdAt: new Date().toISOString(),
      updatedAt: null,
    };
    sessions.set(token, session);
    return session;
  },

  /**
   * Update position for a session.
   * @param {string} token
   * @param {number} lat
   * @param {number} lng
   * @param {number|null} speed
   * @returns {TrackingSession|null}
   */
  updatePosition(token, lat, lng, speed = null) {
    const session = sessions.get(token);
    if (!session || !session.active) return null;
    session.lat = lat;
    session.lng = lng;
    session.speed = speed;
    session.updatedAt = new Date().toISOString();
    return session;
  },

  /**
   * Deactivate (stop) a session.
   * @param {string} token
   * @returns {TrackingSession|null}
   */
  stop(token) {
    const session = sessions.get(token);
    if (!session) return null;
    session.active = false;
    session.updatedAt = new Date().toISOString();
    return session;
  },

  /**
   * Get a session by token.
   * @param {string} token
   * @returns {TrackingSession|null}
   */
  get(token) {
    return sessions.get(token) || null;
  },
};

module.exports = LoadTracking;

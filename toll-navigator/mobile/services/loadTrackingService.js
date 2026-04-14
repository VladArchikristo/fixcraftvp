/**
 * loadTrackingService.js
 *
 * Manages the active load tracking session:
 *  - Stores token in AsyncStorage so it survives app restarts
 *  - Sends GPS position updates to the backend
 *  - Called from LoadTrackingScreen and can be called from background GPS tasks
 *    (e.g. IFTA background location task)
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '../config';

const STORAGE_KEY = '@load_tracking_session';

// Use runtime env var if available (same logic as api.js)
const getApiUrl = () =>
  process.env.EXPO_PUBLIC_API_URL || API_BASE_URL;

const loadTrackingService = {
  /**
   * Start a new tracking session.
   * @param {string} destination
   * @returns {Promise<{ token: string, trackingUrl: string, destination: string }>}
   */
  async startTracking(destination) {
    const apiUrl = getApiUrl();
    const { getToken } = await import('./auth');
    const authToken = await getToken();

    const res = await fetch(`${apiUrl}/api/tracking/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({ destination }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }

    const data = await res.json();

    // Persist session so we can restore after app restart
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({
      token: data.token,
      trackingUrl: data.trackingUrl,
      destination,
    }));

    return data;
  },

  /**
   * Send current GPS coordinates to the backend.
   * Designed to be called from background location tasks.
   *
   * @param {string} token
   * @param {number} lat
   * @param {number} lng
   * @param {number|null} speed  — mph, optional
   * @returns {Promise<void>}
   */
  async sendLocationUpdate(token, lat, lng, speed = null) {
    if (!token) return;
    const apiUrl = getApiUrl();

    try {
      const res = await fetch(`${apiUrl}/api/tracking/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, lat, lng, speed }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.warn('[LoadTracking] update failed:', err.error || res.status);
      }
    } catch (err) {
      // Network errors in background tasks should not crash the app
      console.warn('[LoadTracking] network error during update:', err.message);
    }
  },

  /**
   * Stop the tracking session (mark as delivered).
   * @param {string} token
   * @returns {Promise<void>}
   */
  async stopTracking(token) {
    const apiUrl = getApiUrl();
    const { getToken } = await import('./auth');
    const authToken = await getToken();

    const res = await fetch(`${apiUrl}/api/tracking/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({ token }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }

    // Clear persisted session
    await AsyncStorage.removeItem(STORAGE_KEY);
  },

  /**
   * Retrieve an active session from AsyncStorage (for restore on app launch).
   * @returns {Promise<{ token: string, trackingUrl: string, destination: string }|null>}
   */
  async getActiveSession() {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  /**
   * Clear any stored session locally (without calling the backend).
   * Use when you know the session is already dead server-side.
   */
  async clearSession() {
    await AsyncStorage.removeItem(STORAGE_KEY);
  },
};

export { loadTrackingService };
export default loadTrackingService;

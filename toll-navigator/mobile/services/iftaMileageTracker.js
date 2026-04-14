/**
 * IFTA Mileage Tracker
 * Receives GPS batches from the background location task,
 * calculates distances using the Haversine formula,
 * and persists accumulated miles per state in SQLite.
 *
 * SQLite table: ifta_mileage
 *   id          INTEGER PRIMARY KEY AUTOINCREMENT
 *   date        TEXT     — ISO date string (YYYY-MM-DD), used for quarterly grouping
 *   state_code  TEXT     — 2-letter state abbreviation (TX, CA, …)
 *   miles       REAL     — accumulated miles for this date+state row
 *   lat         REAL     — last known latitude in this state segment
 *   lng         REAL     — last known longitude in this state segment
 *   timestamp   INTEGER  — Unix ms timestamp of the last GPS point in this segment
 *
 * Compatibility: the `date` column maps to trip `created_at` used in quarterlyCalculator.js.
 * The `state_code` column maps to the state keys used in IFTA_TAX_RATES.
 */

import * as SQLite from 'expo-sqlite';
import { detectState } from './stateDetectionService';

// ─────────────────────────────────────────────────────────────────────────────
// Database init
// ─────────────────────────────────────────────────────────────────────────────

let _db = null;

/**
 * Open (or reuse) the SQLite database and ensure the ifta_mileage table exists.
 * @returns {Promise<SQLite.SQLiteDatabase>}
 */
async function getDb() {
  if (_db) return _db;

  _db = await SQLite.openDatabaseAsync('toll_navigator.db');

  await _db.execAsync(`
    CREATE TABLE IF NOT EXISTS ifta_mileage (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      date       TEXT    NOT NULL,
      state_code TEXT    NOT NULL,
      miles      REAL    NOT NULL DEFAULT 0,
      lat        REAL,
      lng        REAL,
      timestamp  INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_ifta_mileage_date_state
      ON ifta_mileage (date, state_code);
  `);

  // Table for tracking the last recorded GPS point (used between task wake-ups)
  await _db.execAsync(`
    CREATE TABLE IF NOT EXISTS ifta_tracking_state (
      key   TEXT PRIMARY KEY,
      value TEXT
    );
  `);

  return _db;
}

// ─────────────────────────────────────────────────────────────────────────────
// Haversine distance formula
// ─────────────────────────────────────────────────────────────────────────────

const EARTH_RADIUS_MILES = 3958.8;

/**
 * Calculate great-circle distance between two GPS points in miles.
 *
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {number} distance in miles
 */
function haversineDistanceMiles(lat1, lng1, lat2, lng2) {
  const toRad = (deg) => (deg * Math.PI) / 180;

  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return EARTH_RADIUS_MILES * c;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tracking state persistence (last recorded point)
// ─────────────────────────────────────────────────────────────────────────────

async function getLastPoint() {
  const db = await getDb();
  const row = await db.getFirstAsync(
    `SELECT value FROM ifta_tracking_state WHERE key = 'last_point'`
  );
  if (!row) return null;
  try {
    return JSON.parse(row.value);
  } catch {
    return null;
  }
}

async function saveLastPoint(point) {
  const db = await getDb();
  await db.runAsync(
    `INSERT OR REPLACE INTO ifta_tracking_state (key, value) VALUES ('last_point', ?)`,
    [JSON.stringify(point)]
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Core: accumulate miles in SQLite
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Add miles to an existing ifta_mileage row, or insert a new one.
 *
 * @param {string} date        ISO date (YYYY-MM-DD)
 * @param {string} stateCode   e.g. 'TX'
 * @param {number} miles
 * @param {number} lat
 * @param {number} lng
 * @param {number} timestamp   Unix ms
 */
async function accumulateMiles(date, stateCode, miles, lat, lng, timestamp) {
  const db = await getDb();

  const existing = await db.getFirstAsync(
    `SELECT id, miles FROM ifta_mileage WHERE date = ? AND state_code = ?`,
    [date, stateCode]
  );

  if (existing) {
    await db.runAsync(
      `UPDATE ifta_mileage SET miles = miles + ?, lat = ?, lng = ?, timestamp = ?
       WHERE id = ?`,
      [miles, lat, lng, timestamp, existing.id]
    );
  } else {
    await db.runAsync(
      `INSERT INTO ifta_mileage (date, state_code, miles, lat, lng, timestamp)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [date, stateCode, miles, lat, lng, timestamp]
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Process a batch of GPS locations from the background task.
 * Called by backgroundLocationService.js inside the TaskManager task.
 *
 * @param {Array<{ coords: { latitude, longitude }, timestamp: number }>} locations
 */
export async function processBatchedLocations(locations) {
  if (!locations || locations.length === 0) return;

  // Sort chronologically (TaskManager may deliver in any order)
  const sorted = [...locations].sort((a, b) => a.timestamp - b.timestamp);

  let prevPoint = await getLastPoint();

  for (const loc of sorted) {
    const { latitude, longitude } = loc.coords;
    const ts = loc.timestamp;

    if (!prevPoint) {
      // First point ever — just record it as starting position
      prevPoint = { latitude, longitude, timestamp: ts };
      await saveLastPoint(prevPoint);
      continue;
    }

    // Skip duplicate or near-zero-distance points
    const dist = haversineDistanceMiles(
      prevPoint.latitude,
      prevPoint.longitude,
      latitude,
      longitude
    );

    // Ignore implausible jumps (>300 miles between 40s polls = plane speed)
    // or GPS noise (<0.01 miles = ~53 feet)
    if (dist < 0.01 || dist > 300) {
      prevPoint = { latitude, longitude, timestamp: ts };
      await saveLastPoint(prevPoint);
      continue;
    }

    // Detect state at the current point
    const detected = detectState(latitude, longitude);
    if (!detected) {
      // Outside US — still update prevPoint
      prevPoint = { latitude, longitude, timestamp: ts };
      await saveLastPoint(prevPoint);
      continue;
    }

    const { state: stateCode } = detected;
    const date = new Date(ts).toISOString().slice(0, 10); // YYYY-MM-DD

    await accumulateMiles(date, stateCode, dist, latitude, longitude, ts);

    prevPoint = { latitude, longitude, timestamp: ts };
  }

  // Persist the last processed point for next task wake-up
  if (prevPoint) {
    await saveLastPoint(prevPoint);
  }
}

/**
 * Get accumulated mileage by state for a date range.
 * Compatible with quarterlyCalculator.js — returns the same shape as state_miles.
 *
 * @param {string} startDate  ISO date (YYYY-MM-DD)
 * @param {string} endDate    ISO date (YYYY-MM-DD)
 * @returns {Promise<Array<{ state_code: string, miles: number }>>}
 */
export async function getMileageByState(startDate, endDate) {
  const db = await getDb();
  const rows = await db.getAllAsync(
    `SELECT state_code, SUM(miles) as miles
     FROM ifta_mileage
     WHERE date >= ? AND date <= ?
     GROUP BY state_code
     ORDER BY state_code`,
    [startDate, endDate]
  );
  return rows || [];
}

/**
 * Get total miles logged today across all states.
 * @returns {Promise<number>}
 */
export async function getTodayMiles() {
  const db = await getDb();
  const today = new Date().toISOString().slice(0, 10);
  const row = await db.getFirstAsync(
    `SELECT COALESCE(SUM(miles), 0) as total FROM ifta_mileage WHERE date = ?`,
    [today]
  );
  return parseFloat((row?.total ?? 0).toFixed(2));
}

/**
 * Get the most recently detected state code.
 * @returns {Promise<string|null>}
 */
export async function getCurrentState() {
  try {
    const lastPoint = await getLastPoint();
    if (!lastPoint) return null;
    const detected = detectState(lastPoint.latitude, lastPoint.longitude);
    return detected?.state ?? null;
  } catch {
    return null;
  }
}

/**
 * Delete all IFTA mileage records (use with caution — for testing/reset only).
 */
export async function clearAllMileageData() {
  const db = await getDb();
  await db.execAsync(`
    DELETE FROM ifta_mileage;
    DELETE FROM ifta_tracking_state;
  `);
}

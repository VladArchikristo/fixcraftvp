/**
 * Background Location Service
 * Registers and manages background GPS tracking for automatic IFTA mileage logging.
 *
 * ⚠️  IMPORTANT: Background tasks work ONLY with EAS Build (expo-dev-client or standalone build).
 *     They do NOT work in Expo Go. Use `eas build` to test this feature.
 *
 * Dependencies required in package.json:
 *   expo-location: ~17.0.1
 *   expo-task-manager: ~12.0.1
 */

import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import { processBatchedLocations } from './iftaMileageTracker';

export const BACKGROUND_LOCATION_TASK = 'BACKGROUND_LOCATION_TASK';

/**
 * Define the background task.
 * Must be called at the root level (outside any component/function)
 * so that TaskManager can register it on app launch.
 */
TaskManager.defineTask(BACKGROUND_LOCATION_TASK, async ({ data, error }) => {
  if (error) {
    console.error('[BGLocation] Task error:', error.message);
    return;
  }

  if (!data) {
    console.warn('[BGLocation] Task received no data');
    return;
  }

  const { locations } = data;
  if (!locations || locations.length === 0) return;

  try {
    // Pass GPS points to IFTA mileage tracker for processing
    await processBatchedLocations(locations);
  } catch (err) {
    console.error('[BGLocation] Failed to process locations:', err.message);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Permission helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Request foreground + background location permissions.
 * Returns { granted: boolean, needsSettings: boolean, message: string }
 */
export async function requestLocationPermissions() {
  // Step 1: Foreground permission (required first on both platforms)
  const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
  if (fgStatus !== 'granted') {
    return {
      granted: false,
      needsSettings: false,
      message:
        'Location permission denied. Go to Settings → Toll Navigator → Location and allow "While Using the App".',
    };
  }

  // Step 2: Background permission
  const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
  if (bgStatus !== 'granted') {
    return {
      granted: false,
      needsSettings: true,
      message:
        'Background location denied. Go to Settings → Toll Navigator → Location and select "Always".',
    };
  }

  return { granted: true, needsSettings: false, message: '' };
}

/**
 * Check current permission status without prompting.
 * Returns { foreground: boolean, background: boolean }
 */
export async function checkLocationPermissions() {
  const fg = await Location.getForegroundPermissionsAsync();
  const bg = await Location.getBackgroundPermissionsAsync();
  return {
    foreground: fg.status === 'granted',
    background: bg.status === 'granted',
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Start / Stop tracking
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Start background GPS tracking.
 * Polls every 40 seconds or every ~50 meters traveled (whichever comes first).
 *
 * @returns {{ success: boolean, error?: string }}
 */
export async function startBackgroundTracking() {
  try {
    const { granted, message } = await requestLocationPermissions();
    if (!granted) {
      return { success: false, error: message };
    }

    // Check if already running
    const isRegistered = await TaskManager.isTaskRegisteredAsync(BACKGROUND_LOCATION_TASK);
    if (isRegistered) {
      console.log('[BGLocation] Task already registered, skipping start');
      return { success: true };
    }

    await Location.startLocationUpdatesAsync(BACKGROUND_LOCATION_TASK, {
      accuracy: Location.Accuracy.Balanced,     // Good balance of accuracy vs. battery
      timeInterval: 40000,                       // Minimum 40 seconds between updates
      distanceInterval: 50,                      // Or 50 meters traveled
      showsBackgroundLocationIndicator: true,    // iOS: blue bar indicating background tracking
      foregroundService: {
        // Android: foreground service notification keeps process alive
        notificationTitle: 'Toll Navigator — IFTA Tracking',
        notificationBody: 'Recording miles by state for IFTA report',
        notificationColor: '#1565c0',
      },
      pausesUpdatesAutomatically: false,         // Keep tracking on highways
    });

    console.log('[BGLocation] Background tracking started');
    return { success: true };
  } catch (err) {
    console.error('[BGLocation] Failed to start:', err.message);
    return { success: false, error: err.message };
  }
}

/**
 * Stop background GPS tracking.
 * @returns {{ success: boolean, error?: string }}
 */
export async function stopBackgroundTracking() {
  try {
    const isRegistered = await TaskManager.isTaskRegisteredAsync(BACKGROUND_LOCATION_TASK);
    if (!isRegistered) {
      console.log('[BGLocation] Task not running, nothing to stop');
      return { success: true };
    }

    await Location.stopLocationUpdatesAsync(BACKGROUND_LOCATION_TASK);
    console.log('[BGLocation] Background tracking stopped');
    return { success: true };
  } catch (err) {
    console.error('[BGLocation] Failed to stop:', err.message);
    return { success: false, error: err.message };
  }
}

/**
 * Check if background tracking is currently active.
 * @returns {Promise<boolean>}
 */
export async function isTrackingActive() {
  try {
    return await TaskManager.isTaskRegisteredAsync(BACKGROUND_LOCATION_TASK);
  } catch {
    return false;
  }
}

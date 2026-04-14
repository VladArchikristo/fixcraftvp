/**
 * State Detection Service
 * Determines which US state a GPS coordinate falls in using bounding boxes.
 *
 * Strategy:
 *   1. Fast pass: check approximate bounding box for each of the 48 contiguous states
 *      + Alaska + Hawaii.
 *   2. Returns the best candidate (smallest bounding box area that contains the point)
 *      to resolve overlap ambiguities at borders.
 *
 * Accuracy: bounding boxes are a good approximation for IFTA purposes.
 * Border crossings within ~10-20 miles may occasionally be misclassified —
 * acceptable for mileage accumulation (driver can manually adjust rare edge cases).
 */

// ─────────────────────────────────────────────────────────────────────────────
// Bounding boxes: [minLat, maxLat, minLng, maxLng]
// Source: approximate state extents, sufficient for IFTA mileage detection.
// ─────────────────────────────────────────────────────────────────────────────
const STATE_BOUNDS = {
  AL: { name: 'Alabama',       bounds: [30.14, 35.01, -88.47, -84.89] },
  AK: { name: 'Alaska',        bounds: [54.56, 71.54, -169.94, -129.99] },
  AZ: { name: 'Arizona',       bounds: [31.33, 37.00, -114.82, -109.04] },
  AR: { name: 'Arkansas',      bounds: [33.00, 36.50, -94.62, -89.64] },
  CA: { name: 'California',    bounds: [32.53, 42.01, -124.41, -114.13] },
  CO: { name: 'Colorado',      bounds: [36.99, 41.00, -109.06, -102.04] },
  CT: { name: 'Connecticut',   bounds: [40.95, 42.05, -73.73, -71.79] },
  DE: { name: 'Delaware',      bounds: [38.45, 39.84, -75.79, -75.05] },
  FL: { name: 'Florida',       bounds: [24.52, 31.00, -87.63, -80.03] },
  GA: { name: 'Georgia',       bounds: [30.36, 35.00, -85.61, -80.84] },
  HI: { name: 'Hawaii',        bounds: [18.91, 22.24, -160.25, -154.81] },
  ID: { name: 'Idaho',         bounds: [41.99, 49.00, -117.24, -111.04] },
  IL: { name: 'Illinois',      bounds: [36.97, 42.51, -91.51, -87.02] },
  IN: { name: 'Indiana',       bounds: [37.77, 41.76, -88.10, -84.78] },
  IA: { name: 'Iowa',          bounds: [40.37, 43.50, -96.64, -90.14] },
  KS: { name: 'Kansas',        bounds: [36.99, 40.00, -102.05, -94.59] },
  KY: { name: 'Kentucky',      bounds: [36.50, 39.15, -89.57, -81.96] },
  LA: { name: 'Louisiana',     bounds: [28.92, 33.02, -94.04, -88.82] },
  ME: { name: 'Maine',         bounds: [43.06, 47.46, -71.08, -66.95] },
  MD: { name: 'Maryland',      bounds: [37.91, 39.72, -79.49, -75.05] },
  MA: { name: 'Massachusetts', bounds: [41.24, 42.89, -73.51, -69.93] },
  MI: { name: 'Michigan',      bounds: [41.70, 48.19, -90.42, -82.41] },
  MN: { name: 'Minnesota',     bounds: [43.50, 49.38, -97.24, -89.49] },
  MS: { name: 'Mississippi',   bounds: [30.17, 34.99, -91.65, -88.10] },
  MO: { name: 'Missouri',      bounds: [35.99, 40.61, -95.77, -89.10] },
  MT: { name: 'Montana',       bounds: [44.36, 49.00, -116.05, -104.04] },
  NE: { name: 'Nebraska',      bounds: [39.99, 43.00, -104.05, -95.31] },
  NV: { name: 'Nevada',        bounds: [35.00, 42.00, -120.01, -114.04] },
  NH: { name: 'New Hampshire', bounds: [42.70, 45.31, -72.56, -70.61] },
  NJ: { name: 'New Jersey',    bounds: [38.93, 41.36, -75.56, -74.05] },
  NM: { name: 'New Mexico',    bounds: [31.33, 37.00, -109.05, -103.00] },
  NY: { name: 'New York',      bounds: [40.50, 45.01, -79.10, -71.86] },
  NC: { name: 'North Carolina',bounds: [33.84, 36.59, -84.32, -75.46] },
  ND: { name: 'North Dakota',  bounds: [45.93, 49.00, -104.05, -96.55] },
  OH: { name: 'Ohio',          bounds: [38.40, 42.33, -84.82, -80.52] },
  OK: { name: 'Oklahoma',      bounds: [34.01, 37.00, -103.00, -94.43] },
  OR: { name: 'Oregon',        bounds: [41.99, 46.24, -124.57, -116.46] },
  PA: { name: 'Pennsylvania',  bounds: [39.72, 42.27, -80.52, -74.69] },
  RI: { name: 'Rhode Island',  bounds: [41.15, 42.02, -71.91, -71.12] },
  SC: { name: 'South Carolina',bounds: [32.03, 35.22, -83.36, -78.54] },
  SD: { name: 'South Dakota',  bounds: [42.48, 45.95, -104.06, -96.44] },
  TN: { name: 'Tennessee',     bounds: [34.98, 36.68, -90.31, -81.65] },
  TX: { name: 'Texas',         bounds: [25.84, 36.50, -106.65, -93.51] },
  UT: { name: 'Utah',          bounds: [36.99, 42.00, -114.05, -109.04] },
  VT: { name: 'Vermont',       bounds: [42.73, 45.02, -73.44, -71.46] },
  VA: { name: 'Virginia',      bounds: [36.54, 39.47, -83.68, -75.24] },
  WA: { name: 'Washington',    bounds: [45.54, 49.00, -124.73, -116.92] },
  WV: { name: 'West Virginia', bounds: [37.20, 40.64, -82.64, -77.72] },
  WI: { name: 'Wisconsin',     bounds: [42.49, 47.08, -92.89, -86.25] },
  WY: { name: 'Wyoming',       bounds: [40.99, 45.01, -111.06, -104.05] },
};

/**
 * Detect which US state a GPS coordinate is in.
 *
 * @param {number} latitude
 * @param {number} longitude
 * @returns {{ state: string, stateName: string } | null}
 *   Returns null if the coordinate is outside all known state bounds (e.g., Canada, Mexico, ocean).
 */
export function detectState(latitude, longitude) {
  const lat = parseFloat(latitude);
  const lng = parseFloat(longitude);

  if (isNaN(lat) || isNaN(lng)) return null;

  const candidates = [];

  for (const [code, { name, bounds }] of Object.entries(STATE_BOUNDS)) {
    const [minLat, maxLat, minLng, maxLng] = bounds;
    if (lat >= minLat && lat <= maxLat && lng >= minLng && lng <= maxLng) {
      // Calculate bounding box area to prefer smaller (more specific) states
      const area = (maxLat - minLat) * (maxLng - minLng);
      candidates.push({ state: code, stateName: name, area });
    }
  }

  if (candidates.length === 0) return null;

  // Pick the candidate with the smallest bounding box (most specific)
  candidates.sort((a, b) => a.area - b.area);
  const { state, stateName } = candidates[0];
  return { state, stateName };
}

/**
 * Detect a state boundary crossing between two GPS points.
 *
 * @param {{ latitude: number, longitude: number }} prevPoint
 * @param {{ latitude: number, longitude: number }} currPoint
 * @returns {{ crossed: boolean, from: string|null, to: string|null }}
 */
export function detectStateCrossing(prevPoint, currPoint) {
  if (!prevPoint || !currPoint) {
    return { crossed: false, from: null, to: null };
  }

  const prev = detectState(prevPoint.latitude, prevPoint.longitude);
  const curr = detectState(currPoint.latitude, currPoint.longitude);

  if (!prev || !curr) {
    return { crossed: false, from: prev?.state ?? null, to: curr?.state ?? null };
  }

  if (prev.state !== curr.state) {
    return { crossed: true, from: prev.state, to: curr.state };
  }

  return { crossed: false, from: prev.state, to: curr.state };
}

/**
 * Get full state name by abbreviation.
 * @param {string} code  e.g. 'TX'
 * @returns {string}
 */
export function getStateName(code) {
  return STATE_BOUNDS[code]?.name ?? code;
}

/**
 * List all supported state codes.
 * @returns {string[]}
 */
export function getSupportedStates() {
  return Object.keys(STATE_BOUNDS);
}

const express = require('express');
const { verifyToken } = require('../middleware/auth');
const { calculateTollCost, getTollsByState, getAvailableStates } = require('../services/tollCalculator');
const db = require('../db');
const cache = require('../services/cache');

const router = express.Router();

// Карта популярных городов → штат (abbr)
const CITY_STATE_MAP = {
  // Texas
  'dallas': 'TX', 'houston': 'TX', 'austin': 'TX', 'san antonio': 'TX',
  'fort worth': 'TX', 'el paso': 'TX', 'arlington': 'TX', 'corpus christi': 'TX',
  // California
  'los angeles': 'CA', 'la': 'CA', 'san francisco': 'CA', 'san diego': 'CA',
  'sacramento': 'CA', 'fresno': 'CA', 'long beach': 'CA', 'oakland': 'CA',
  // Florida
  'miami': 'FL', 'orlando': 'FL', 'tampa': 'FL', 'jacksonville': 'FL',
  'fort lauderdale': 'FL', 'tallahassee': 'FL', 'st. petersburg': 'FL',
  // New York
  'new york': 'NY', 'nyc': 'NY', 'buffalo': 'NY', 'rochester': 'NY', 'albany': 'NY',
  // Illinois
  'chicago': 'IL', 'aurora': 'IL', 'rockford': 'IL', 'joliet': 'IL',
  // Pennsylvania
  'philadelphia': 'PA', 'pittsburgh': 'PA', 'allentown': 'PA', 'erie': 'PA',
  // Ohio
  'columbus': 'OH', 'cleveland': 'OH', 'cincinnati': 'OH', 'toledo': 'OH',
  // Georgia
  'atlanta': 'GA', 'savannah': 'GA', 'augusta': 'GA', 'macon': 'GA',
  // North Carolina
  'charlotte': 'NC', 'raleigh': 'NC', 'greensboro': 'NC', 'durham': 'NC',
  // New Jersey
  'newark': 'NJ', 'jersey city': 'NJ', 'trenton': 'NJ', 'camden': 'NJ',
  // Virginia
  'virginia beach': 'VA', 'norfolk': 'VA', 'richmond': 'VA', 'arlington': 'VA',
  // Tennessee
  'nashville': 'TN', 'memphis': 'TN', 'knoxville': 'TN', 'chattanooga': 'TN',
  // Louisiana
  'new orleans': 'LA', 'baton rouge': 'LA', 'shreveport': 'LA',
  // Oklahoma
  'oklahoma city': 'OK', 'tulsa': 'OK',
  // Kansas
  'wichita': 'KS', 'overland park': 'KS', 'kansas city': 'KS',
  // Maryland
  'baltimore': 'MD', 'annapolis': 'MD', 'rockville': 'MD', 'gaithersburg': 'MD', 'columbia': 'MD',
  // Massachusetts
  'boston': 'MA', 'worcester': 'MA', 'springfield': 'MA', 'cambridge': 'MA', 'lowell': 'MA',
  // Indiana
  'indianapolis': 'IN', 'fort wayne': 'IN', 'south bend': 'IN', 'evansville': 'IN', 'gary': 'IN',
  // Colorado
  'denver': 'CO', 'colorado springs': 'CO', 'aurora': 'CO', 'fort collins': 'CO',
  // Arizona
  'phoenix': 'AZ', 'tucson': 'AZ', 'scottsdale': 'AZ', 'mesa': 'AZ', 'chandler': 'AZ',
  // Washington
  'seattle': 'WA', 'spokane': 'WA', 'tacoma': 'WA', 'bellevue': 'WA',
  // Nevada
  'las vegas': 'NV', 'reno': 'NV', 'henderson': 'NV',
  // Oklahoma
  'oklahoma city': 'OK', 'tulsa': 'OK', 'norman': 'OK', 'broken arrow': 'OK',
  // Georgia (extra cities)
  'columbus': 'GA',
  // Virginia
  'virginia beach': 'VA', 'norfolk': 'VA', 'richmond': 'VA', 'roanoke': 'VA',
  'alexandria': 'VA', 'chesapeake': 'VA', 'hampton': 'VA',
  // New Jersey
  'newark': 'NJ', 'jersey city': 'NJ', 'trenton': 'NJ', 'camden': 'NJ',
  'paterson': 'NJ', 'elizabeth': 'NJ', 'atlantic city': 'NJ',
  // Michigan
  'detroit': 'MI', 'grand rapids': 'MI', 'warren': 'MI', 'sterling heights': 'MI',
  'ann arbor': 'MI', 'lansing': 'MI',
  // Minnesota
  'minneapolis': 'MN', 'saint paul': 'MN', 'duluth': 'MN',
  // Wisconsin
  'milwaukee': 'WI', 'madison': 'WI', 'green bay': 'WI', 'kenosha': 'WI',
  // Missouri
  'kansas city': 'MO', 'st. louis': 'MO', 'columbia': 'MO',
  // Alabama
  'birmingham': 'AL', 'montgomery': 'AL', 'huntsville': 'AL', 'mobile': 'AL',
  // South Carolina
  'charleston': 'SC', 'greenville': 'SC', 'spartanburg': 'SC',
  // Kentucky
  'louisville': 'KY', 'lexington': 'KY', 'bowling green': 'KY',
  // Connecticut
  'bridgeport': 'CT', 'new haven': 'CT', 'hartford': 'CT', 'stamford': 'CT',
  // Iowa
  'des moines': 'IA', 'cedar rapids': 'IA', 'davenport': 'IA', 'sioux city': 'IA',
  // Arkansas
  'little rock': 'AR', 'fort smith': 'AR', 'fayetteville': 'AR',
  // Mississippi
  'jackson': 'MS', 'gulfport': 'MS', 'hattiesburg': 'MS',
  // Utah
  'salt lake city': 'UT', 'west valley city': 'UT', 'provo': 'UT',
  'west jordan': 'UT', 'orem': 'UT',
  // New Mexico
  'albuquerque': 'NM', 'las cruces': 'NM', 'rio rancho': 'NM', 'santa fe': 'NM',
  // Nebraska
  'omaha': 'NE', 'lincoln': 'NE', 'bellevue': 'NE',
  // West Virginia
  'huntington': 'WV', 'morgantown': 'WV',
  // Idaho
  'boise': 'ID', 'meridian': 'ID', 'nampa': 'ID', 'idaho falls': 'ID',
  // Hawaii
  'honolulu': 'HI', 'hilo': 'HI', 'kailua': 'HI', 'pearl city': 'HI',
  // Alaska
  'anchorage': 'AK', 'fairbanks': 'AK', 'juneau': 'AK',
};

// Примерные расстояния между популярными маршрутами (мили)
const ROUTE_DISTANCES = {
  // Texas
  'TX-TX': 260, 'TX-LA': 350, 'TX-OK': 200, 'TX-NM': 290, 'TX-AR': 310,
  'TX-GA': 900, 'TX-FL': 1050, 'TX-TN': 850, 'TX-NC': 1100,
  // California
  'CA-CA': 380, 'CA-NV': 270, 'CA-AZ': 380, 'CA-OR': 590,
  'CA-TX': 1560, 'CA-IL': 2020, 'CA-NY': 2800,
  // Florida
  'FL-FL': 280, 'FL-GA': 350, 'FL-AL': 400, 'FL-SC': 500,
  'FL-NC': 750, 'FL-VA': 950, 'FL-MD': 1080, 'FL-NJ': 1200, 'FL-NY': 1280,
  // New York
  'NY-NJ': 50, 'NY-PA': 160, 'NY-CT': 80, 'NY-MA': 220,
  'NY-MD': 200, 'NY-VA': 360, 'NY-NC': 570, 'NY-GA': 900,
  // Illinois
  'IL-IN': 180, 'IL-OH': 320, 'IL-MO': 290, 'IL-WI': 150,
  'IL-PA': 460, 'IL-NY': 790, 'IL-MI': 280, 'IL-KY': 350,
  // Pennsylvania
  'PA-NJ': 90, 'PA-MD': 120, 'PA-OH': 320, 'PA-NY': 160,
  'PA-VA': 250, 'PA-NC': 500, 'PA-MA': 380, 'PA-DE': 50,
  // Ohio
  'OH-PA': 320, 'OH-IN': 180, 'OH-KY': 100, 'OH-MI': 145,
  'OH-WV': 140, 'OH-NY': 400, 'OH-IL': 320,
  // Georgia
  'GA-FL': 350, 'GA-TN': 120, 'GA-AL': 160, 'GA-NC': 250,
  'GA-SC': 180, 'GA-VA': 420, 'GA-TX': 900,
  // North Carolina
  'NC-VA': 200, 'NC-SC': 120, 'NC-TN': 380, 'NC-GA': 250,
  'NC-MD': 380, 'NC-NY': 560, 'NC-NJ': 480,
  // New Jersey
  'NJ-NY': 50, 'NJ-PA': 90, 'NJ-MD': 150, 'NJ-DE': 80,
  'NJ-VA': 280, 'NJ-MA': 290,
  // Virginia
  'VA-MD': 120, 'VA-NC': 200, 'VA-WV': 200, 'VA-TN': 340,
  'VA-PA': 250, 'VA-NJ': 280, 'VA-NY': 360,
  // Massachusetts
  'MA-NH': 60, 'MA-RI': 50, 'MA-CT': 100, 'MA-NY': 220,
  'MA-PA': 380, 'MA-NJ': 290, 'MA-MD': 430,
  // Maryland
  'MD-VA': 120, 'MD-PA': 120, 'MD-DE': 100, 'MD-NJ': 150,
  'MD-DC': 40, 'MD-WV': 180, 'MD-NY': 200,
  // Indiana
  'IN-OH': 180, 'IN-IL': 180, 'IN-KY': 120, 'IN-MI': 200,
  'IN-WI': 210, 'IN-PA': 430,
  // Oklahoma
  'OK-TX': 200, 'OK-KS': 170, 'OK-AR': 200, 'OK-MO': 260,
  'OK-CO': 420, 'OK-NM': 380,
  // Colorado
  'CO-CO': 110, 'CO-NM': 280, 'CO-KS': 340, 'CO-WY': 100,
  'CO-UT': 370, 'CO-NV': 730, 'CO-AZ': 580, 'CO-TX': 670,
  'CO-OK': 420, 'CO-CA': 1230, 'CO-IL': 1000,
  // Washington
  'WA-WA': 150, 'WA-OR': 180, 'WA-ID': 280, 'WA-MT': 430,
  'WA-CA': 820, 'WA-NV': 900, 'WA-CO': 1200,
  // Arizona
  'AZ-AZ': 170, 'AZ-NV': 280, 'AZ-UT': 360, 'AZ-NM': 290,
  'AZ-CA': 380, 'AZ-TX': 870, 'AZ-CO': 580,
  // Nevada
  'NV-NV': 300, 'NV-CA': 270, 'NV-AZ': 280, 'NV-UT': 420,
  'NV-OR': 500, 'NV-ID': 550, 'NV-WA': 900, 'NV-CO': 730,
  // Minnesota
  'MN-MN': 200, 'MN-WI': 280, 'MN-IA': 250, 'MN-ND': 290,
  'MN-SD': 220, 'MN-IL': 420, 'MN-IN': 530, 'MN-OH': 740,
  // City-to-city routes
  'dallas-kansas city': 480, 'kansas city-dallas': 480,
  'dallas-oklahoma city': 200, 'oklahoma city-dallas': 200,
  'houston-baton rouge': 270, 'baton rouge-houston': 270,
  'atlanta-birmingham': 150, 'birmingham-atlanta': 150,
  'atlanta-columbia': 215, 'columbia-atlanta': 215,
  'charlotte-columbia': 90, 'columbia-charlotte': 90,
  'miami-tampa': 280, 'tampa-miami': 280,
  'miami-jacksonville': 345, 'jacksonville-miami': 345,
  'chicago-milwaukee': 90, 'milwaukee-chicago': 90,
  'chicago-minneapolis': 410, 'minneapolis-chicago': 410,
  'chicago-detroit': 280, 'detroit-chicago': 280,
  'detroit-cleveland': 170, 'cleveland-detroit': 170,
  'cleveland-pittsburgh': 130, 'pittsburgh-cleveland': 130,
  'boston-hartford': 100, 'hartford-boston': 100,
  'boston-providence': 50, 'providence-boston': 50,
  'seattle-portland': 175, 'portland-seattle': 175,
  'portland-sacramento': 580, 'sacramento-portland': 580,
  'salt lake city-denver': 525, 'denver-salt lake city': 525,
  'albuquerque-phoenix': 425, 'phoenix-albuquerque': 425,
  'las vegas-salt lake city': 420, 'salt lake city-las vegas': 420,
  'denver-kansas city': 600, 'kansas city-denver': 600,
  'omaha-kansas city': 185, 'kansas city-omaha': 185,
  'indianapolis-chicago': 180, 'chicago-indianapolis': 180,
  'indianapolis-columbus': 175, 'columbus-indianapolis': 175,
  'nashville-birmingham': 185, 'birmingham-nashville': 185,
  'nashville-memphis': 210, 'memphis-nashville': 210,
  'new orleans-baton rouge': 80, 'baton rouge-new orleans': 80,
  'richmond-washington': 115, 'washington-richmond': 115,
  'baltimore-philadelphia': 100, 'philadelphia-baltimore': 100,
  'philadelphia-new york': 95, 'new york-philadelphia': 95,
};

function parseCity(input) {
  if (!input) return null;
  const parts = input.split(',');
  const city = parts[0].trim().toLowerCase();
  const stateHint = parts[1] ? parts[1].trim().toUpperCase() : null;

  // Если явно указан штат (Dallas, TX)
  if (stateHint && stateHint.length === 2) return stateHint;

  return CITY_STATE_MAP[city] || null;
}

function estimateDistance(fromState, toState) {
  const key1 = `${fromState}-${toState}`;
  const key2 = `${toState}-${fromState}`;
  return ROUTE_DISTANCES[key1] || ROUTE_DISTANCES[key2] || 400;
}

// Interstate highway corridors — промежуточные штаты для основных трак-маршрутов
const CORRIDORS = {
  // I-95 East Coast (South→North)
  'FL-GA': ['FL', 'GA'],
  'FL-SC': ['FL', 'GA', 'SC'],
  'FL-NC': ['FL', 'GA', 'SC', 'NC'],
  'FL-VA': ['FL', 'GA', 'SC', 'NC', 'VA'],
  'FL-MD': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD'],
  'FL-DE': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE'],
  'FL-NJ': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ'],
  'FL-NY': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ', 'NY'],
  'FL-MA': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ', 'NY', 'CT', 'MA'],
  'GA-NC': ['GA', 'SC', 'NC'],
  'GA-VA': ['GA', 'SC', 'NC', 'VA'],
  'GA-MD': ['GA', 'SC', 'NC', 'VA', 'MD'],
  'GA-NJ': ['GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ'],
  'GA-NY': ['GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ', 'NY'],
  'NC-VA': ['NC', 'VA'],
  'NC-MD': ['NC', 'VA', 'MD'],
  'NC-NJ': ['NC', 'VA', 'MD', 'DE', 'NJ'],
  'NC-NY': ['NC', 'VA', 'MD', 'DE', 'NJ', 'NY'],
  'VA-MD': ['VA', 'MD'],
  'VA-NJ': ['VA', 'MD', 'DE', 'NJ'],
  'VA-NY': ['VA', 'MD', 'DE', 'NJ', 'NY'],
  'VA-MA': ['VA', 'MD', 'DE', 'NJ', 'NY', 'CT', 'MA'],
  'MD-NJ': ['MD', 'DE', 'NJ'],
  'MD-NY': ['MD', 'DE', 'NJ', 'NY'],
  'MD-MA': ['MD', 'DE', 'NJ', 'NY', 'CT', 'MA'],
  'NJ-NY': ['NJ', 'NY'],
  'NJ-MA': ['NJ', 'NY', 'CT', 'MA'],
  'NY-MA': ['NY', 'CT', 'MA'],
  // I-90 / I-80 Midwest (West→East)
  'IL-IN': ['IL', 'IN'],
  'IL-OH': ['IL', 'IN', 'OH'],
  'IL-PA': ['IL', 'IN', 'OH', 'PA'],
  'IL-NY': ['IL', 'IN', 'OH', 'PA', 'NY'],
  'IL-MA': ['IL', 'IN', 'OH', 'PA', 'NY', 'MA'],
  'IL-NJ': ['IL', 'IN', 'OH', 'PA', 'NJ'],
  'IN-OH': ['IN', 'OH'],
  'IN-PA': ['IN', 'OH', 'PA'],
  'IN-NY': ['IN', 'OH', 'PA', 'NY'],
  'IN-NJ': ['IN', 'OH', 'PA', 'NJ'],
  'OH-PA': ['OH', 'PA'],
  'OH-NY': ['OH', 'PA', 'NY'],
  'OH-NJ': ['OH', 'PA', 'NJ'],
  'OH-MA': ['OH', 'PA', 'NY', 'MA'],
  'OH-MD': ['OH', 'PA', 'MD'],
  'OH-VA': ['OH', 'PA', 'MD', 'VA'],
  'PA-NY': ['PA', 'NY'],
  'PA-NJ': ['PA', 'NJ'],
  'PA-MA': ['PA', 'NY', 'MA'],
  'PA-MD': ['PA', 'MD'],
  'PA-VA': ['PA', 'MD', 'VA'],
  // South (I-20/I-40 East-West)
  'TX-LA': ['TX', 'LA'],
  'TX-MS': ['TX', 'LA', 'MS'],
  'TX-AL': ['TX', 'LA', 'MS', 'AL'],
  'TX-GA': ['TX', 'LA', 'MS', 'AL', 'GA'],
  'TX-TN': ['TX', 'AR', 'TN'],
  'TX-NC': ['TX', 'LA', 'MS', 'AL', 'GA', 'NC'],
  'TX-OK': ['TX', 'OK'],
  'TX-AR': ['TX', 'AR'],
  'OK-MO': ['OK', 'AR', 'MO'],
  'OK-TN': ['OK', 'AR', 'TN'],
  'OK-IL': ['OK', 'MO', 'IL'],
  // CA cross-country
  'CA-AZ': ['CA', 'AZ'],
  'CA-NM': ['CA', 'AZ', 'NM'],
  'CA-TX': ['CA', 'AZ', 'NM', 'TX'],
  'CA-OK': ['CA', 'AZ', 'NM', 'TX', 'OK'],
  'CA-IL': ['CA', 'AZ', 'NM', 'TX', 'OK', 'MO', 'IL'],
  'CA-IN': ['CA', 'AZ', 'NM', 'TX', 'OK', 'MO', 'IL', 'IN'],
  'CA-OH': ['CA', 'AZ', 'NM', 'TX', 'OK', 'MO', 'IL', 'IN', 'OH'],
  'CA-PA': ['CA', 'AZ', 'NM', 'TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA'],
  'CA-NY': ['CA', 'AZ', 'NM', 'TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA', 'NJ', 'NY'],
  // TX cross-country (east)
  'TX-NC': ['TX', 'LA', 'MS', 'AL', 'GA', 'SC', 'NC'],
  'TX-VA': ['TX', 'LA', 'MS', 'AL', 'GA', 'SC', 'NC', 'VA'],
  'TX-PA': ['TX', 'LA', 'MS', 'AL', 'GA', 'SC', 'NC', 'VA', 'MD', 'PA'],
  'TX-NY': ['TX', 'LA', 'MS', 'AL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'NJ', 'NY'],
  // West Coast / Mountain corridors
  'CA-NV': ['CA', 'NV'],
  'CA-CO': ['CA', 'NV', 'CO'],
  'CA-MN': ['CA', 'NV', 'CO', 'MN'],
  'NV-AZ': ['NV', 'AZ'],
  'NV-CO': ['NV', 'CO'],
  'NV-TX': ['NV', 'AZ', 'NM', 'TX'],
  'AZ-NM': ['AZ', 'NM'],
  'AZ-TX': ['AZ', 'NM', 'TX'],
  'AZ-CO': ['AZ', 'CO'],
  'CO-TX': ['CO', 'OK', 'TX'],
  'CO-OK': ['CO', 'OK'],
  'CO-IL': ['CO', 'MO', 'IL'],
  'CO-MN': ['CO', 'NE', 'MN'],
  // Pacific Northwest
  'WA-CA': ['WA', 'OR', 'CA'],
  'WA-NV': ['WA', 'OR', 'CA', 'NV'],
  'WA-CO': ['WA', 'ID', 'MT', 'WY', 'CO'],
  // Midwest MN routes
  'MN-IL': ['MN', 'WI', 'IL'],
  'MN-IN': ['MN', 'WI', 'IL', 'IN'],
  'MN-OH': ['MN', 'WI', 'IL', 'IN', 'OH'],
  'MN-PA': ['MN', 'WI', 'IL', 'IN', 'OH', 'PA'],
  'MN-NY': ['MN', 'WI', 'IL', 'IN', 'OH', 'PA', 'NY'],
};

function getStatesBetween(fromState, toState) {
  if (fromState === toState) return [fromState];

  // Ищем готовый коридор
  const keyFwd = `${fromState}-${toState}`;
  const keyRev = `${toState}-${fromState}`;

  if (CORRIDORS[keyFwd]) return CORRIDORS[keyFwd];
  if (CORRIDORS[keyRev]) return [...CORRIDORS[keyRev]].reverse();

  // Фоллбэк — два штата
  return [fromState, toState];
}

/**
 * GET /api/tolls/route?from=Dallas,TX&to=Houston,TX&truck_type=5-axle
 * Удобный эндпоинт — принимает города, возвращает расчёт
 */
router.get('/route', (req, res) => {
  // Опциональная авторизация — сохраняем историю если пользователь залогинен
  let userId = null;
  try {
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const jwt = require('jsonwebtoken');
      const decoded = jwt.verify(authHeader.slice(7), process.env.JWT_SECRET);
      userId = decoded.userId || decoded.id;
    }
  } catch (_) { /* не авторизован — ок, продолжаем без сохранения */ }

  try {
    const { from, to, truck_type, axles } = req.query;

    // Input validation
    if (!from || !to) {
      return res.status(400).json({ error: 'Parameters "from" and "to" are required' });
    }
    if (from.length > 100 || to.length > 100) {
      return res.status(400).json({ error: 'City names too long' });
    }
    // Normalize truck_type: accept both "2axle" and "2-axle" formats
    const normalizeTruckType = (t) => t ? t.replace(/-/g, '') : '5axle';
    const validTruckTypes = ['2axle', '3axle', '4axle', '5axle', '6axle'];
    const truckType = normalizeTruckType(truck_type || '5axle');
    if (!validTruckTypes.includes(truckType)) {
      return res.status(400).json({ error: `Invalid truck_type. Must be one of: ${validTruckTypes.join(', ')} (or with dashes: 2-axle, 5-axle)` });
    }

    // --- Cache check ---
    const cacheKey = cache.routeCacheKey(from, to, truckType);
    const cached = cache.get(cacheKey);
    if (cached) {
      // Добавляем признак кэша, но не сохраняем в историю повторно
      return res.json({ ...cached, cached: true });
    }

    const fromState = parseCity(from);
    const toState = parseCity(to);

    if (!fromState) {
      return res.status(400).json({ error: `Unknown city: "${from}". Use format "Dallas,TX"` });
    }
    if (!toState) {
      return res.status(400).json({ error: `Unknown city: "${to}". Use format "Houston,TX"` });
    }

    const states = getStatesBetween(fromState, toState);
    const distanceMiles = estimateDistance(fromState, toState);
    const availableStates = getAvailableStates();
    const filteredStates = states.filter(s => availableStates.includes(s));

    if (filteredStates.length === 0) {
      const emptyResult = {
        from, to,
        from_state: fromState,
        to_state: toState,
        distance_miles: distanceMiles,
        total: 0,
        message: 'No toll roads found on this route',
        breakdown: [],
      };
      cache.set(cacheKey, emptyResult);
      return res.status(200).json(emptyResult);
    }

    const result = calculateTollCost(filteredStates, distanceMiles, truckType);

    const response = {
      from,
      to,
      from_state: fromState,
      to_state: toState,
      distance_miles: distanceMiles,
      ...result,
    };

    // Кэшируем результат (TTL 1 час)
    cache.set(cacheKey, response);

    // Сохраняем в историю если пользователь авторизован
    if (userId) {
      try {
        db.prepare(
          'INSERT INTO routes (user_id, from_city, to_city, truck_type, total_toll, distance_miles, states_crossed) VALUES (?, ?, ?, ?, ?, ?, ?)'
        ).run(userId, from, to, truckType, result.total, distanceMiles, JSON.stringify(filteredStates));
      } catch (dbErr) {
        console.warn('History save failed:', dbErr.message);
      }
    }

    res.json(response);
  } catch (err) {
    console.error('Route calculate error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

/**
 * POST /api/tolls/calculate
 * Рассчитать стоимость толлов
 * Body: { states: ['TX', 'LA'], distance_miles: 500, truck_type: '5-axle' }
 */
router.post('/calculate', verifyToken, (req, res) => {
  try {
    const { states, distance_miles, truck_type = '2-axle', origin = '', destination = '' } = req.body;

    if (!states || !Array.isArray(states) || states.length === 0) {
      return res.status(400).json({ error: 'states array is required (e.g. ["TX", "LA"])' });
    }
    if (!distance_miles || distance_miles <= 0) {
      return res.status(400).json({ error: 'distance_miles must be a positive number' });
    }

    const validStates = getAvailableStates();
    const unknown = states.filter(s => !validStates.includes(s.toUpperCase()));
    if (unknown.length > 0) {
      return res.status(400).json({
        error: `No toll data for states: ${unknown.join(', ')}`,
        available_states: validStates,
      });
    }

    const result = calculateTollCost(
      states.map(s => s.toUpperCase()),
      parseFloat(distance_miles),
      truck_type
    );

    // Сохраняем маршрут в историю
    db.prepare(
      'INSERT INTO routes (user_id, from_city, to_city, truck_type, total_toll, distance_miles, states_crossed) VALUES (?, ?, ?, ?, ?, ?, ?)'
    ).run(
      req.userId,
      origin || states[0],
      destination || states[states.length - 1],
      truck_type,
      result.total,
      distance_miles,
      JSON.stringify(result.states_crossed)
    );

    res.json(result);
  } catch (err) {
    console.error('Calculate error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

/**
 * GET /api/tolls/states
 * Список штатов с данными
 */
router.get('/states', (req, res) => {
  res.json({ states: getAvailableStates() });
});

/**
 * GET /api/tolls/state/:code
 * Toll дороги конкретного штата
 */
router.get('/state/:code', (req, res) => {
  const roads = getTollsByState(req.params.code);
  if (roads.length === 0) {
    return res.status(404).json({ error: 'No data for this state' });
  }
  res.json({ state: req.params.code.toUpperCase(), roads });
});

/**
 * GET /api/tolls/history
 * История маршрутов текущего пользователя
 */
router.get('/history', verifyToken, (req, res) => {
  const routes = db.prepare(
    'SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC LIMIT 20'
  ).all(req.userId);
  res.json(routes);
});

// Save route to history
router.post('/history', verifyToken, (req, res) => {
  const { from_city, to_city, truck_type, total_toll, distance_miles, route_data } = req.body;

  if (!from_city || !to_city || !truck_type) {
    return res.status(400).json({ error: 'Missing required fields: from_city, to_city, truck_type' });
  }

  try {
    const result = db.prepare(
      `INSERT INTO routes (user_id, from_city, to_city, truck_type, total_toll, distance_miles, route_data, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))`
    ).run(req.userId, from_city, to_city, truck_type, total_toll || 0, distance_miles || 0, route_data ? JSON.stringify(route_data) : null);

    res.status(201).json({
      success: true,
      id: result.lastInsertRowid,
      message: 'Route saved to history'
    });
  } catch (err) {
    console.error('Error saving history:', err);
    res.status(500).json({ error: 'Failed to save route' });
  }
});

module.exports = router;

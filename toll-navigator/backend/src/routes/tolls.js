const express = require('express');
const { verifyToken } = require('../middleware/auth');
const { calculateTollCost, getTollsByState, getAvailableStates } = require('../services/tollCalculator');
const { getRealRoute, getStatesAlongRoute, calculateStateMilesFromWaypoints, getStateBounds } = require('../services/geoService');
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

// ─────────────────────────────────────────────────────────────────────────────
// Точные расстояния между городами (мили по шоссе, реальные данные)
// Ключ: "City1,ST|City2,ST" (нижний регистр, оба направления заносятся ниже)
// ─────────────────────────────────────────────────────────────────────────────
const ROUTE_DISTANCES = {
  // Dallas ↔ *
  'dallas,tx|new york,ny': 1571, 'dallas,tx|los angeles,ca': 1435, 'dallas,tx|chicago,il': 921,
  'dallas,tx|miami,fl': 1311, 'dallas,tx|atlanta,ga': 781, 'dallas,tx|houston,tx': 239,
  'dallas,tx|san antonio,tx': 274, 'dallas,tx|austin,tx': 196, 'dallas,tx|el paso,tx': 625,
  'dallas,tx|albuquerque,nm': 638, 'dallas,tx|phoenix,az': 1027, 'dallas,tx|memphis,tn': 452,
  'dallas,tx|oklahoma city,ok': 207, 'dallas,tx|little rock,ar': 316, 'dallas,tx|kansas city,mo': 499,
  // Houston ↔ *
  'houston,tx|new york,ny': 1627, 'houston,tx|los angeles,ca': 1553, 'houston,tx|chicago,il': 1092,
  'houston,tx|san antonio,tx': 199, 'houston,tx|austin,tx': 162, 'houston,tx|new orleans,la': 349,
  'houston,tx|dallas,tx': 239,
  // New York ↔ *
  'new york,ny|los angeles,ca': 2790, 'new york,ny|chicago,il': 789, 'new york,ny|miami,fl': 1281,
  'new york,ny|atlanta,ga': 874, 'new york,ny|boston,ma': 215, 'new york,ny|philadelphia,pa': 95,
  'new york,ny|baltimore,md': 195, 'new york,ny|washington dc,dc': 228, 'new york,ny|richmond,va': 354,
  'new york,ny|charlotte,nc': 633, 'new york,ny|pittsburgh,pa': 371, 'new york,ny|detroit,mi': 613,
  'new york,ny|buffalo,ny': 375, 'new york,ny|nashville,tn': 889, 'new york,ny|columbus,oh': 503,
  // Los Angeles ↔ *
  'los angeles,ca|chicago,il': 2016, 'los angeles,ca|miami,fl': 2757, 'los angeles,ca|phoenix,az': 372,
  'los angeles,ca|las vegas,nv': 270, 'los angeles,ca|seattle,wa': 1137, 'los angeles,ca|san francisco,ca': 381,
  'los angeles,ca|sacramento,ca': 386, 'los angeles,ca|salt lake city,ut': 689,
  'los angeles,ca|denver,co': 1021, 'los angeles,ca|albuquerque,nm': 791,
  // Chicago ↔ *
  'chicago,il|atlanta,ga': 716, 'chicago,il|miami,fl': 1379, 'chicago,il|seattle,wa': 2064,
  'chicago,il|denver,co': 1003, 'chicago,il|nashville,tn': 476, 'chicago,il|detroit,mi': 281,
  'chicago,il|pittsburgh,pa': 452, 'chicago,il|columbus,oh': 351, 'chicago,il|indianapolis,in': 181,
  'chicago,il|milwaukee,wi': 92, 'chicago,il|minneapolis,mn': 409, 'chicago,il|kansas city,mo': 503,
  'chicago,il|st louis,mo': 300, 'chicago,il|cleveland,oh': 345, 'chicago,il|memphis,tn': 530,
  'chicago,il|des moines,ia': 335,
  // Atlanta ↔ *
  'atlanta,ga|miami,fl': 662, 'atlanta,ga|charlotte,nc': 245, 'atlanta,ga|nashville,tn': 249,
  'atlanta,ga|birmingham,al': 148, 'atlanta,ga|new orleans,la': 469, 'atlanta,ga|savannah,ga': 249,
  'atlanta,ga|jacksonville,fl': 346,
  // Seattle ↔ *
  'seattle,wa|chicago,il': 2064, 'seattle,wa|los angeles,ca': 1137, 'seattle,wa|portland,or': 174,
  'seattle,wa|boise,id': 497, 'seattle,wa|denver,co': 1321,
  // Denver ↔ *
  'denver,co|chicago,il': 1003, 'denver,co|los angeles,ca': 1021, 'denver,co|salt lake city,ut': 527,
  'denver,co|minneapolis,mn': 917, 'denver,co|billings,mt': 549, 'denver,co|cheyenne,wy': 99,
  'denver,co|seattle,wa': 1321,
  // Phoenix ↔ *
  'phoenix,az|los angeles,ca': 372, 'phoenix,az|dallas,tx': 1027, 'phoenix,az|tucson,az': 116,
  // Las Vegas ↔ *
  'las vegas,nv|los angeles,ca': 270, 'las vegas,nv|salt lake city,ut': 419,
  // Nashville ↔ *
  'nashville,tn|atlanta,ga': 249, 'nashville,tn|chicago,il': 476, 'nashville,tn|new york,ny': 889,
  'nashville,tn|birmingham,al': 191, 'nashville,tn|louisville,ky': 176,
  'nashville,tn|washington dc,dc': 660,
  // Memphis ↔ *
  'memphis,tn|dallas,tx': 452, 'memphis,tn|chicago,il': 530, 'memphis,tn|little rock,ar': 138,
  // Kansas City ↔ *
  'kansas city,mo|chicago,il': 503, 'kansas city,mo|dallas,tx': 499, 'kansas city,mo|st louis,mo': 253,
  'kansas city,mo|omaha,ne': 187, 'kansas city,mo|oklahoma city,ok': 337,
  // Minneapolis ↔ *
  'minneapolis,mn|chicago,il': 409, 'minneapolis,mn|denver,co': 917, 'minneapolis,mn|sioux falls,sd': 244,
  'minneapolis,mn|fargo,nd': 235,
  // Detroit ↔ *
  'detroit,mi|chicago,il': 281, 'detroit,mi|new york,ny': 613,
  // Pittsburgh ↔ *
  'pittsburgh,pa|new york,ny': 371, 'pittsburgh,pa|chicago,il': 452, 'pittsburgh,pa|cleveland,oh': 131,
  // Columbus ↔ *
  'columbus,oh|chicago,il': 351, 'columbus,oh|new york,ny': 503, 'columbus,oh|indianapolis,in': 176,
  'columbus,oh|cincinnati,oh': 108,
  // Charlotte ↔ *
  'charlotte,nc|atlanta,ga': 245, 'charlotte,nc|new york,ny': 633,
  // Baltimore ↔ *
  'baltimore,md|new york,ny': 195,
  // Philadelphia ↔ *
  'philadelphia,pa|new york,ny': 95, 'philadelphia,pa|washington dc,dc': 140,
  // Boston ↔ *
  'boston,ma|new york,ny': 215, 'boston,ma|miami,fl': 1494,
  // Portland ↔ *
  'portland,or|seattle,wa': 174, 'portland,or|san francisco,ca': 640,
  // San Francisco ↔ *
  'san francisco,ca|los angeles,ca': 381, 'san francisco,ca|sacramento,ca': 88,
  'san francisco,ca|reno,nv': 219,
  // Sacramento ↔ *
  'sacramento,ca|los angeles,ca': 386,
  // Tucson ↔ *
  'tucson,az|phoenix,az': 116,
  // Oklahoma City ↔ *
  'oklahoma city,ok|dallas,tx': 207, 'oklahoma city,ok|kansas city,mo': 337,
  // Little Rock ↔ *
  'little rock,ar|memphis,tn': 138, 'little rock,ar|dallas,tx': 316,
  // New Orleans ↔ *
  'new orleans,la|houston,tx': 349, 'new orleans,la|atlanta,ga': 469,
  // Birmingham ↔ *
  'birmingham,al|atlanta,ga': 148, 'birmingham,al|nashville,tn': 191,
  // Jacksonville ↔ *
  'jacksonville,fl|miami,fl': 341, 'jacksonville,fl|atlanta,ga': 346,
  // Orlando ↔ *
  'orlando,fl|miami,fl': 236,
  // Tampa ↔ *
  'tampa,fl|miami,fl': 281,
  // Savannah ↔ *
  'savannah,ga|atlanta,ga': 249,
  // Richmond ↔ *
  'richmond,va|washington dc,dc': 108, 'richmond,va|new york,ny': 354,
  // Washington DC ↔ *
  'washington dc,dc|new york,ny': 228, 'washington dc,dc|philadelphia,pa': 140,
  // Buffalo ↔ *
  'buffalo,ny|new york,ny': 375,
  // Cleveland ↔ *
  'cleveland,oh|pittsburgh,pa': 131, 'cleveland,oh|chicago,il': 345,
  // Indianapolis ↔ *
  'indianapolis,in|chicago,il': 181, 'indianapolis,in|columbus,oh': 176,
  'indianapolis,in|louisville,ky': 115,
  // Louisville ↔ *
  'louisville,ky|nashville,tn': 176, 'louisville,ky|indianapolis,in': 115,
  'louisville,ky|cincinnati,oh': 100,
  // Cincinnati ↔ *
  'cincinnati,oh|columbus,oh': 108, 'cincinnati,oh|louisville,ky': 100,
  // St Louis ↔ *
  'st louis,mo|kansas city,mo': 253, 'st louis,mo|chicago,il': 300,
  // Milwaukee ↔ *
  'milwaukee,wi|chicago,il': 92, 'milwaukee,wi|green bay,wi': 116,
  // Green Bay ↔ *
  'green bay,wi|milwaukee,wi': 116,
  // Des Moines ↔ *
  'des moines,ia|chicago,il': 335,
  // Omaha ↔ *
  'omaha,ne|kansas city,mo': 187,
  // Sioux Falls ↔ *
  'sioux falls,sd|minneapolis,mn': 244,
  // Fargo ↔ *
  'fargo,nd|minneapolis,mn': 235,
  // Billings ↔ *
  'billings,mt|denver,co': 549,
  // Cheyenne ↔ *
  'cheyenne,wy|denver,co': 99, 'cheyenne,wy|salt lake city,ut': 440,
  // Salt Lake City ↔ *
  'salt lake city,ut|denver,co': 527, 'salt lake city,ut|los angeles,ca': 689,
  'salt lake city,ut|las vegas,nv': 419,
  // Boise ↔ *
  'boise,id|seattle,wa': 497,
  // Reno ↔ *
  'reno,nv|san francisco,ca': 219,
  // Albuquerque ↔ *
  'albuquerque,nm|dallas,tx': 638, 'albuquerque,nm|los angeles,ca': 791,
  // El Paso ↔ *
  'el paso,tx|dallas,tx': 625,
  // San Antonio ↔ *
  'san antonio,tx|dallas,tx': 274, 'san antonio,tx|houston,tx': 199,
  // Austin ↔ *
  'austin,tx|dallas,tx': 196, 'austin,tx|houston,tx': 162,
};

// ─────────────────────────────────────────────────────────────────────────────
// Распределение миль по штатам для маршрутов (STATE_MILES)
// Ключ: "City1,ST|City2,ST" — значение: объект { штат: мили }
// ─────────────────────────────────────────────────────────────────────────────
const STATE_MILES = {
  // Dallas→NY: северный маршрут I-35→I-44→I-70→I-76/I-78 (реальный трак-маршрут)
  'dallas,tx|new york,ny': { TX: 200, OK: 340, MO: 300, IL: 150, IN: 170, OH: 190, PA: 155, NJ: 90, NY: 66 },
  'dallas,tx|los angeles,ca': { TX: 350, NM: 290, AZ: 420, CA: 375 },
  'dallas,tx|chicago,il': { TX: 200, OK: 200, MO: 380, IL: 141 },
  'dallas,tx|miami,fl': { TX: 250, LA: 200, MS: 150, AL: 120, FL: 591 },
  'dallas,tx|atlanta,ga': { TX: 250, LA: 180, MS: 150, AL: 120, GA: 81 },
  'dallas,tx|houston,tx': { TX: 239 },
  'dallas,tx|san antonio,tx': { TX: 274 },
  'dallas,tx|austin,tx': { TX: 196 },
  'dallas,tx|el paso,tx': { TX: 625 },
  'dallas,tx|albuquerque,nm': { TX: 350, NM: 288 },
  'dallas,tx|phoenix,az': { TX: 350, NM: 290, AZ: 387 },
  'dallas,tx|memphis,tn': { TX: 100, AR: 120, TN: 232 },
  'dallas,tx|oklahoma city,ok': { TX: 30, OK: 177 },
  'dallas,tx|little rock,ar': { TX: 30, AR: 286 },
  'dallas,tx|kansas city,mo': { TX: 30, OK: 200, MO: 269 },
  'houston,tx|new york,ny': { TX: 450, LA: 200, MS: 150, AL: 120, GA: 150, SC: 100, NC: 150, VA: 120, MD: 50, DE: 35, NJ: 55, NY: 47 },
  'houston,tx|los angeles,ca': { TX: 500, NM: 290, AZ: 420, CA: 343 },
  'houston,tx|chicago,il': { TX: 200, OK: 200, MO: 420, IL: 272 },
  'houston,tx|san antonio,tx': { TX: 199 },
  'houston,tx|austin,tx': { TX: 162 },
  'houston,tx|new orleans,la': { TX: 170, LA: 179 },
  'new york,ny|los angeles,ca': { NY: 150, NJ: 55, PA: 300, OH: 220, IN: 150, IL: 150, MO: 280, OK: 200, TX: 350, NM: 290, AZ: 420, CA: 225 },
  'new york,ny|chicago,il': { NY: 100, NJ: 30, PA: 200, OH: 180, IN: 120, IL: 159 },
  'new york,ny|miami,fl': { NY: 100, NJ: 55, DE: 50, MD: 90, VA: 120, NC: 250, SC: 200, GA: 100, FL: 316 },
  'new york,ny|atlanta,ga': { NY: 100, NJ: 55, DE: 50, MD: 90, VA: 120, NC: 200, SC: 110, GA: 149 },
  'new york,ny|boston,ma': { NY: 50, CT: 90, MA: 75 },
  'new york,ny|philadelphia,pa': { NY: 50, NJ: 45 },
  'new york,ny|baltimore,md': { NY: 30, NJ: 55, DE: 50, MD: 60 },
  'new york,ny|washington dc,dc': { NY: 50, NJ: 55, DE: 50, MD: 70, DC: 3 },
  'new york,ny|richmond,va': { NY: 50, NJ: 55, DE: 50, MD: 100, VA: 99 },
  'new york,ny|charlotte,nc': { NY: 50, NJ: 55, DE: 50, MD: 100, VA: 200, NC: 178 },
  'new york,ny|pittsburgh,pa': { NY: 100, NJ: 55, PA: 216 },
  'new york,ny|detroit,mi': { NY: 150, PA: 200, OH: 200, MI: 63 },
  'new york,ny|buffalo,ny': { NY: 375 },
  'new york,ny|nashville,tn': { NY: 100, NJ: 55, PA: 300, OH: 220, KY: 100, TN: 114 },
  'new york,ny|columbus,oh': { NY: 100, NJ: 55, PA: 250, OH: 98 },
  'los angeles,ca|chicago,il': { CA: 560, AZ: 400, NM: 200, TX: 150, OK: 280, MO: 280, IL: 146 },
  'los angeles,ca|miami,fl': { CA: 300, AZ: 290, NM: 200, TX: 500, LA: 200, MS: 150, AL: 120, FL: 497 },
  'los angeles,ca|phoenix,az': { CA: 130, AZ: 242 },
  'los angeles,ca|las vegas,nv': { CA: 100, NV: 170 },
  'los angeles,ca|seattle,wa': { CA: 640, OR: 310, WA: 187 },
  'los angeles,ca|san francisco,ca': { CA: 381 },
  'los angeles,ca|sacramento,ca': { CA: 386 },
  'los angeles,ca|salt lake city,ut': { CA: 280, NV: 180, UT: 229 },
  'los angeles,ca|denver,co': { CA: 280, NV: 180, UT: 250, CO: 311 },
  'los angeles,ca|albuquerque,nm': { CA: 200, AZ: 290, NM: 301 },
  'chicago,il|atlanta,ga': { IL: 100, IN: 60, KY: 200, TN: 200, GA: 156 },
  'chicago,il|miami,fl': { IL: 100, IN: 60, KY: 200, TN: 200, GA: 450, FL: 369 },
  'chicago,il|seattle,wa': { IL: 150, MN: 350, ND: 180, MT: 550, ID: 330, WA: 504 },
  'chicago,il|denver,co': { IL: 100, IA: 220, NE: 350, CO: 333 },
  'chicago,il|nashville,tn': { IL: 100, KY: 200, TN: 176 },
  'chicago,il|detroit,mi': { IL: 30, IN: 60, MI: 191 },
  'chicago,il|pittsburgh,pa': { IL: 60, IN: 150, OH: 180, PA: 62 },
  'chicago,il|columbus,oh': { IL: 60, IN: 150, OH: 141 },
  'chicago,il|indianapolis,in': { IL: 90, IN: 91 },
  'chicago,il|milwaukee,wi': { IL: 50, WI: 42 },
  'chicago,il|minneapolis,mn': { IL: 50, WI: 150, MN: 209 },
  'chicago,il|kansas city,mo': { IL: 250, MO: 253 },
  'chicago,il|st louis,mo': { IL: 250, MO: 50 },
  'chicago,il|cleveland,oh': { IL: 30, IN: 150, OH: 165 },
  'chicago,il|memphis,tn': { IL: 100, KY: 200, TN: 230 },
  'chicago,il|des moines,ia': { IL: 150, IA: 185 },
  'atlanta,ga|miami,fl': { GA: 120, FL: 542 },
  'atlanta,ga|charlotte,nc': { GA: 100, NC: 145 },
  'atlanta,ga|nashville,tn': { GA: 100, TN: 149 },
  'atlanta,ga|birmingham,al': { GA: 50, AL: 98 },
  'atlanta,ga|new orleans,la': { GA: 100, AL: 180, MS: 100, LA: 89 },
  'atlanta,ga|savannah,ga': { GA: 249 },
  'atlanta,ga|jacksonville,fl': { GA: 150, FL: 196 },
  'seattle,wa|chicago,il': { WA: 350, MT: 550, ND: 180, MN: 350, WI: 150, IL: 484 },
  'seattle,wa|los angeles,ca': { WA: 187, OR: 310, CA: 640 },
  'seattle,wa|portland,or': { WA: 100, OR: 74 },
  'seattle,wa|boise,id': { WA: 130, ID: 367 },
  'seattle,wa|denver,co': { WA: 300, MT: 120, WY: 560, CO: 341 },
  'denver,co|seattle,wa': { CO: 341, WY: 560, MT: 120, WA: 300 },
  'denver,co|chicago,il': { CO: 200, NE: 350, IA: 220, IL: 233 },
  'denver,co|los angeles,ca': { CO: 200, UT: 350, NV: 180, CA: 291 },
  'denver,co|salt lake city,ut': { CO: 200, UT: 327 },
  'denver,co|minneapolis,mn': { CO: 100, NE: 350, SD: 220, MN: 247 },
  'denver,co|billings,mt': { CO: 100, WY: 300, MT: 149 },
  'denver,co|cheyenne,wy': { CO: 60, WY: 39 },
  'phoenix,az|los angeles,ca': { AZ: 130, CA: 242 },
  'phoenix,az|dallas,tx': { AZ: 200, NM: 290, TX: 537 },
  'phoenix,az|tucson,az': { AZ: 116 },
  'las vegas,nv|los angeles,ca': { NV: 100, CA: 170 },
  'las vegas,nv|salt lake city,ut': { NV: 100, UT: 319 },
  'nashville,tn|atlanta,ga': { TN: 100, GA: 149 },
  'nashville,tn|chicago,il': { TN: 100, KY: 200, IL: 176 },
  'nashville,tn|new york,ny': { TN: 100, KY: 200, OH: 220, PA: 250, NJ: 80, NY: 39 },
  'nashville,tn|birmingham,al': { TN: 100, AL: 91 },
  'nashville,tn|louisville,ky': { TN: 90, KY: 86 },
  'nashville,tn|washington dc,dc': { TN: 300, VA: 350, DC: 10 },
  'memphis,tn|dallas,tx': { TN: 20, AR: 130, TX: 302 },
  'memphis,tn|chicago,il': { TN: 20, KY: 200, IL: 310 },
  'memphis,tn|little rock,ar': { TN: 10, AR: 128 },
  'kansas city,mo|chicago,il': { MO: 250, IL: 253 },
  'kansas city,mo|dallas,tx': { MO: 120, OK: 200, TX: 179 },
  'kansas city,mo|st louis,mo': { MO: 253 },
  'kansas city,mo|omaha,ne': { MO: 30, NE: 157 },
  'kansas city,mo|oklahoma city,ok': { MO: 30, OK: 307 },
  'minneapolis,mn|chicago,il': { MN: 150, WI: 150, IL: 109 },
  'minneapolis,mn|denver,co': { MN: 150, SD: 244, NE: 350, CO: 173 },
  'minneapolis,mn|sioux falls,sd': { MN: 100, SD: 144 },
  'minneapolis,mn|fargo,nd': { MN: 100, ND: 135 },
  'detroit,mi|chicago,il': { MI: 100, IN: 90, IL: 91 },
  'detroit,mi|new york,ny': { MI: 100, OH: 200, PA: 200, NJ: 55, NY: 58 },
  'pittsburgh,pa|new york,ny': { PA: 250, NJ: 55, NY: 66 },
  'pittsburgh,pa|chicago,il': { PA: 100, OH: 180, IN: 110, IL: 62 },
  'pittsburgh,pa|cleveland,oh': { PA: 50, OH: 81 },
  'columbus,oh|chicago,il': { OH: 200, IN: 90, IL: 61 },
  'columbus,oh|new york,ny': { OH: 200, PA: 200, NJ: 55, NY: 48 },
  'columbus,oh|indianapolis,in': { OH: 100, IN: 76 },
  'columbus,oh|cincinnati,oh': { OH: 108 },
  'charlotte,nc|atlanta,ga': { NC: 100, GA: 145 },
  'charlotte,nc|new york,ny': { NC: 100, VA: 200, MD: 100, DE: 50, NJ: 80, NY: 103 },
  'baltimore,md|new york,ny': { MD: 50, DE: 50, NJ: 55, NY: 40 },
  'philadelphia,pa|new york,ny': { PA: 20, NJ: 75 },
  'philadelphia,pa|washington dc,dc': { PA: 20, DE: 30, MD: 80, DC: 10 },
  'boston,ma|new york,ny': { MA: 80, CT: 90, NY: 45 },
  'boston,ma|miami,fl': { MA: 80, CT: 90, NY: 90, NJ: 55, DE: 50, MD: 90, VA: 120, NC: 250, SC: 200, GA: 120, FL: 349 },
  'portland,or|seattle,wa': { OR: 50, WA: 124 },
  'portland,or|san francisco,ca': { OR: 360, CA: 280 },
  'san francisco,ca|los angeles,ca': { CA: 381 },
  'san francisco,ca|sacramento,ca': { CA: 88 },
  'san francisco,ca|reno,nv': { CA: 100, NV: 119 },
  'sacramento,ca|los angeles,ca': { CA: 386 },
  'tucson,az|phoenix,az': { AZ: 116 },
  'oklahoma city,ok|dallas,tx': { OK: 170, TX: 37 },
  'oklahoma city,ok|kansas city,mo': { OK: 100, KS: 100, MO: 137 },
  'little rock,ar|memphis,tn': { AR: 70, TN: 68 },
  'little rock,ar|dallas,tx': { AR: 100, TX: 216 },
  'new orleans,la|houston,tx': { LA: 180, TX: 169 },
  'new orleans,la|atlanta,ga': { LA: 100, MS: 150, AL: 100, GA: 119 },
  'birmingham,al|atlanta,ga': { AL: 80, GA: 68 },
  'birmingham,al|nashville,tn': { AL: 100, TN: 91 },
  'jacksonville,fl|miami,fl': { FL: 341 },
  'jacksonville,fl|atlanta,ga': { FL: 100, GA: 246 },
  'orlando,fl|miami,fl': { FL: 236 },
  'tampa,fl|miami,fl': { FL: 281 },
  'savannah,ga|atlanta,ga': { GA: 249 },
  'richmond,va|washington dc,dc': { VA: 100, DC: 8 },
  'richmond,va|new york,ny': { VA: 100, MD: 100, DE: 50, NJ: 55, NY: 49 },
  'washington dc,dc|new york,ny': { DC: 3, MD: 50, DE: 50, NJ: 75, NY: 50 },
  'washington dc,dc|philadelphia,pa': { DC: 3, MD: 40, DE: 30, PA: 67 },
  'buffalo,ny|new york,ny': { NY: 375 },
  'cleveland,oh|pittsburgh,pa': { OH: 70, PA: 61 },
  'cleveland,oh|chicago,il': { OH: 100, IN: 100, IL: 145 },
  'indianapolis,in|chicago,il': { IN: 100, IL: 81 },
  'indianapolis,in|columbus,oh': { IN: 100, OH: 76 },
  'indianapolis,in|louisville,ky': { IN: 80, KY: 35 },
  'louisville,ky|nashville,tn': { KY: 80, TN: 96 },
  'louisville,ky|indianapolis,in': { KY: 80, IN: 35 },
  'louisville,ky|cincinnati,oh': { KY: 60, OH: 40 },
  'cincinnati,oh|columbus,oh': { OH: 108 },
  'cincinnati,oh|louisville,ky': { OH: 50, KY: 50 },
  'st louis,mo|kansas city,mo': { MO: 253 },
  'st louis,mo|chicago,il': { MO: 20, IL: 280 },
  'milwaukee,wi|chicago,il': { WI: 50, IL: 42 },
  'milwaukee,wi|green bay,wi': { WI: 116 },
  'green bay,wi|milwaukee,wi': { WI: 116 },
  'des moines,ia|chicago,il': { IA: 200, IL: 135 },
  'omaha,ne|kansas city,mo': { NE: 100, MO: 87 },
  'sioux falls,sd|minneapolis,mn': { SD: 100, MN: 144 },
  'fargo,nd|minneapolis,mn': { ND: 100, MN: 135 },
  'billings,mt|denver,co': { MT: 150, WY: 270, CO: 129 },
  'cheyenne,wy|denver,co': { WY: 60, CO: 39 },
  'cheyenne,wy|salt lake city,ut': { WY: 200, UT: 240 },
  'salt lake city,ut|denver,co': { UT: 200, CO: 327 },
  'salt lake city,ut|los angeles,ca': { UT: 200, NV: 180, CA: 309 },
  'salt lake city,ut|las vegas,nv': { UT: 200, NV: 219 },
  'boise,id|seattle,wa': { ID: 200, WA: 297 },
  'reno,nv|san francisco,ca': { NV: 100, CA: 119 },
  'albuquerque,nm|dallas,tx': { NM: 200, TX: 438 },
  'albuquerque,nm|los angeles,ca': { NM: 200, AZ: 280, CA: 311 },
  'el paso,tx|dallas,tx': { TX: 625 },
  'san antonio,tx|dallas,tx': { TX: 274 },
  'san antonio,tx|houston,tx': { TX: 199 },
  'austin,tx|dallas,tx': { TX: 196 },
  'austin,tx|houston,tx': { TX: 162 },
};

// Расстояния между СОСЕДНИМИ штатами (сегменты, мили)
// Используются для расчёта суммы по коридору
const SEGMENT_DISTANCES = {
  // East Coast (реальные расстояния по шоссе)
  'FL-GA': 350, 'GA-SC': 170, 'SC-NC': 220, 'NC-VA': 220, 'VA-MD': 110,
  'MD-DE': 60, 'DE-NJ': 50, 'NJ-NY': 120, 'NY-CT': 100, 'CT-RI': 50,
  'RI-MA': 50, 'MA-NH': 80, 'NH-ME': 110, 'NY-VT': 120, 'VT-NH': 90,
  // Southeast interior
  'FL-AL': 380, 'AL-MS': 180, 'MS-LA': 195, 'LA-TX': 350,
  'GA-AL': 160, 'GA-TN': 120, 'GA-FL': 350,
  'AL-TN': 190, 'MS-TN': 280, 'MS-AR': 180,
  'TN-KY': 160, 'TN-NC': 380, 'TN-VA': 340, 'TN-AR': 280,
  'KY-OH': 140, 'KY-IN': 120, 'KY-IL': 200, 'KY-WV': 190, 'KY-VA': 200,
  'WV-VA': 180, 'WV-OH': 140, 'WV-PA': 160, 'WV-MD': 160,
  // Mid-Atlantic / Northeast (реальные расстояния по шоссе)
  'PA-NJ': 90, 'PA-NY': 320, 'PA-MD': 120, 'PA-WV': 160, 'PA-OH': 190, 'PA-DE': 50,
  'NY-PA': 320, 'NY-NJ': 120, 'NY-MA': 220, 'NY-VT': 120,
  'MD-VA': 120, 'MD-PA': 120, 'MD-DE': 90, 'MD-WV': 160,
  'VA-NC': 200, 'VA-WV': 180, 'VA-TN': 340, 'VA-KY': 200,
  'NC-TN': 380, 'NC-SC': 120, 'NC-GA': 250,
  // Midwest (реальные расстояния по шоссе)
  'OH-IN': 170, 'OH-MI': 145, 'OH-PA': 190, 'OH-WV': 140, 'OH-KY': 100,
  'IN-IL': 150, 'IN-MI': 200, 'IN-KY': 120, 'IN-OH': 170,
  'IL-WI': 150, 'IL-MO': 300, 'IL-KY': 200, 'IL-IN': 150, 'IL-IA': 220,
  'MI-OH': 145, 'MI-IN': 200, 'MI-WI': 290,
  'WI-MN': 280, 'WI-IA': 200, 'WI-IL': 150, 'WI-MI': 290,
  'MN-IA': 250, 'MN-ND': 290, 'MN-SD': 220, 'MN-WI': 280,
  'IA-MO': 200, 'IA-IL': 220, 'IA-WI': 200, 'IA-NE': 300, 'IA-SD': 250,
  'MO-IL': 300, 'MO-KY': 380, 'MO-TN': 320, 'MO-AR': 220, 'MO-OK': 340,
  'MO-KS': 200, 'MO-NE': 350, 'MO-IA': 200,
  // South Central (реальные расстояния по шоссе)
  'TX-OK': 200, 'TX-AR': 310, 'TX-LA': 250, 'TX-NM': 580,
  'OK-KS': 170, 'OK-AR': 200, 'OK-MO': 340, 'OK-CO': 420, 'OK-NM': 380, 'OK-TX': 200,  // OK-MO: реальное 340 миль (I-44)
  'AR-TN': 280, 'AR-MS': 180, 'AR-LA': 280, 'AR-MO': 220, 'AR-OK': 200, 'AR-TX': 310,
  'LA-MS': 200, 'LA-TX': 250, 'LA-AR': 280,
  // Plains & Mountain
  'KS-NE': 200, 'KS-CO': 340, 'KS-MO': 200, 'KS-OK': 170,
  'NE-SD': 200, 'NE-IA': 300, 'NE-MO': 350, 'NE-KS': 200, 'NE-CO': 500, 'NE-WY': 450,
  'SD-ND': 200, 'SD-MN': 220, 'SD-NE': 200, 'SD-WY': 400, 'SD-MT': 380,
  'ND-MN': 290, 'ND-MT': 400, 'ND-SD': 200,
  'CO-NM': 280, 'CO-KS': 340, 'CO-NE': 500, 'CO-WY': 100, 'CO-UT': 370,
  'CO-OK': 420, 'CO-AZ': 580,
  'WY-MT': 350, 'WY-ID': 340, 'WY-UT': 320, 'WY-CO': 100, 'WY-NE': 450, 'WY-SD': 400,
  'MT-ID': 330, 'MT-ND': 400, 'MT-SD': 380, 'MT-WY': 350,
  // West
  'NM-TX': 580, 'NM-OK': 380, 'NM-CO': 280, 'NM-AZ': 390, 'NM-UT': 500,
  'AZ-CA': 500, 'AZ-NV': 280, 'AZ-UT': 360, 'AZ-NM': 390,
  'UT-NV': 420, 'UT-ID': 300, 'UT-WY': 320, 'UT-CO': 450, 'UT-AZ': 360,
  'NV-CA': 450, 'NV-AZ': 280, 'NV-UT': 420, 'NV-OR': 500, 'NV-ID': 550,
  'CA-OR': 650, 'CA-NV': 450, 'CA-AZ': 500,
  'OR-WA': 280, 'OR-ID': 340, 'OR-NV': 500, 'OR-CA': 650,
  'WA-OR': 280, 'WA-ID': 280, 'WA-MT': 430,
  'ID-MT': 330, 'ID-WY': 340, 'ID-UT': 300, 'ID-OR': 340, 'ID-NV': 550, 'ID-WA': 280,
  // Alaska / Hawaii (no land routes)
  'AK-AK': 500, 'HI-HI': 200,
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

/**
 * Строит нормализованный ключ для поиска в ROUTE_DISTANCES / STATE_MILES.
 * Порядок не важен — пробуем оба направления.
 */
function routeKey(fromCity, toCity) {
  // Нормализуем: "Dallas, TX" → "dallas,tx" (убираем пробел после запятой)
  const normalize = (s) => s.trim().toLowerCase().replace(/,\s+/g, ',');
  const a = normalize(fromCity);
  const b = normalize(toCity);
  return `${a}|${b}`;
}

/**
 * Ищет точное расстояние по парам городов в таблице ROUTE_DISTANCES.
 * Возвращает { distance, stateMiles } или null если не найдено.
 */
function lookupRouteDistance(from, to) {
  const k1 = routeKey(from, to);
  const k2 = routeKey(to, from);

  if (ROUTE_DISTANCES[k1] !== undefined) {
    return { distance: ROUTE_DISTANCES[k1], stateMiles: STATE_MILES[k1] || null };
  }
  if (ROUTE_DISTANCES[k2] !== undefined) {
    // Обратный маршрут — STATE_MILES тоже разворачиваем (объект, порядок не важен)
    return { distance: ROUTE_DISTANCES[k2], stateMiles: STATE_MILES[k2] || null };
  }
  return null;
}

/**
 * Рассчитывает расстояние как сумму сегментов коридора.
 * Сначала проверяет точную таблицу ROUTE_DISTANCES.
 */
function estimateDistance(fromState, toState, corridorStates, fromCity, toCity) {
  // 1) Точная таблица по городам
  if (fromCity && toCity) {
    const exact = lookupRouteDistance(fromCity, toCity);
    if (exact) return exact.distance;
  }

  if (fromState === toState) return 300; // внутриштатный рейс

  // 2) Если есть коридор — считаем сумму сегментов
  if (corridorStates && corridorStates.length > 1) {
    let total = 0;
    for (let i = 0; i < corridorStates.length - 1; i++) {
      const s1 = corridorStates[i];
      const s2 = corridorStates[i + 1];
      const key1 = `${s1}-${s2}`;
      const key2 = `${s2}-${s1}`;
      const segDist = SEGMENT_DISTANCES[key1] || SEGMENT_DISTANCES[key2] || 200;
      total += segDist;
    }
    return total;
  }

  // 3) Фоллбэк — прямая пара штатов
  const key1 = `${fromState}-${toState}`;
  const key2 = `${toState}-${fromState}`;
  return SEGMENT_DISTANCES[key1] || SEGMENT_DISTANCES[key2] || 500;
}

/**
 * Возвращает распределение миль по штатам для маршрута.
 * Если есть в таблице STATE_MILES — используем её.
 * Иначе — делим поровну по коридору.
 */
function getStateMiles(fromCity, toCity, corridorStates, totalDistance) {
  if (fromCity && toCity) {
    const k1 = routeKey(fromCity, toCity);
    const k2 = routeKey(toCity, fromCity);
    if (STATE_MILES[k1]) return STATE_MILES[k1];
    if (STATE_MILES[k2]) return STATE_MILES[k2];
  }
  // Фоллбэк: поровну
  const perState = Math.round(totalDistance / (corridorStates.length || 1));
  const result = {};
  corridorStates.forEach(s => { result[s] = perState; });
  return result;
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
  // TX cross-country (north/east — реальный трак-маршрут I-35/I-44/I-70)
  'TX-OK': ['TX', 'OK'],
  'TX-MO': ['TX', 'OK', 'MO'],
  'TX-IL': ['TX', 'OK', 'MO', 'IL'],
  'TX-IN': ['TX', 'OK', 'MO', 'IL', 'IN'],
  'TX-OH': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH'],
  'TX-PA': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA'],
  'TX-NJ': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA', 'NJ'],
  'TX-NY': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA', 'NJ', 'NY'],
  'TX-NC': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA', 'MD', 'VA', 'NC'],
  'TX-VA': ['TX', 'OK', 'MO', 'IL', 'IN', 'OH', 'PA', 'MD', 'VA'],
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
 * Shared route handler — используется и GET, и POST /route
 * ASYNC: сначала пробует реальное расстояние через OSRM (Nominatim + OpenStreetMap),
 * при недоступности — fallback на hardcoded таблицы ROUTE_DISTANCES
 */
async function handleRoute(params, headers, res, db, cache) {
  // Опциональная авторизация — сохраняем историю если пользователь залогинен
  let userId = null;
  try {
    const authHeader = headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const jwt = require('jsonwebtoken');
      const decoded = jwt.verify(authHeader.slice(7), process.env.JWT_SECRET);
      userId = decoded.userId || decoded.id;
    }
  } catch (_) {}

  try {
    const { from, to, truck_type } = params;

    if (!from || !to) {
      return res.status(400).json({ error: 'Parameters "from" and "to" are required' });
    }
    if (from.length > 100 || to.length > 100) {
      return res.status(400).json({ error: 'City names too long' });
    }

    // Normalize truck_type: accept both "2axle" and "2-axle" formats → always output "2-axle" style
    const normalizeTruckType = (t) => {
      if (!t) return '5-axle';
      // Add dash if missing: "5axle" → "5-axle"
      return t.replace(/^(\d)(-?)axle$/, '$1-axle');
    };
    const validTruckTypes = ['2-axle', '3-axle', '4-axle', '5-axle', '6-axle'];
    const truckType = normalizeTruckType(truck_type || '5-axle');
    if (!validTruckTypes.includes(truckType)) {
      return res.status(400).json({ error: `Invalid truck_type. Must be one of: ${validTruckTypes.join(', ')} (or without dashes: 2axle, 5axle)` });
    }

    const cacheKey = cache.routeCacheKey(from, to, truckType);
    const cached = cache.get(cacheKey);
    if (cached) return res.json({ ...cached, cached: true });

    const fromState = parseCity(from);
    const toState = parseCity(to);

    if (!fromState) return res.status(400).json({ error: `Unknown city: "${from}". Use format "Dallas,TX"` });
    if (!toState) return res.status(400).json({ error: `Unknown city: "${to}". Use format "Houston,TX"` });

    // ── ТОЧНЫЙ РАСЧЁТ через OSRM (OpenStreetMap) ─────────────────────────────
    let distanceMiles;
    let durationHours = null;
    let distanceSource = 'table'; // 'osrm' | 'table' | 'estimated'
    let states;

    const realRoute = await getRealRoute(from, to);

    let osrmStateMiles = null; // точные мили по штатам от OSRM waypoints

    if (realRoute && realRoute.distanceMiles > 0) {
      // Реальное расстояние по дорогам от OSRM
      distanceMiles = realRoute.distanceMiles;
      durationHours = realRoute.durationHours;
      distanceSource = 'osrm';

      // Определяем штаты по реальным waypoints (реальный путь по дорогам)
      if (realRoute.fromCoords && realRoute.toCoords) {
        const geoResult = getStatesAlongRoute(realRoute.fromCoords, realRoute.toCoords, realRoute.waypoints);
        states = geoResult.states.length > 0 ? geoResult.states : getStatesBetween(fromState, toState);

        // Точные мили по штатам из waypoints OSRM
        if (realRoute.waypoints && realRoute.waypoints.length > 1) {
          osrmStateMiles = calculateStateMilesFromWaypoints(realRoute.waypoints, distanceMiles, getStateBounds());
        }
      } else {
        states = getStatesBetween(fromState, toState);
      }
    } else {
      // Fallback: hardcoded таблицы ROUTE_DISTANCES → SEGMENT_DISTANCES
      states = getStatesBetween(fromState, toState);
      const estimatedDist = estimateDistance(fromState, toState, states, from, to);
      distanceMiles = estimatedDist;
      distanceSource = lookupRouteDistance(from, to) ? 'table' : 'estimated';
    }
    // ─────────────────────────────────────────────────────────────────────────

    // Приоритет: точные мили OSRM → hardcoded таблица → равномерное деление
    const stateMilesMap = osrmStateMiles || getStateMiles(from, to, states, distanceMiles);
    const availableStates = getAvailableStates();
    const filteredStates = states.filter(s => availableStates.includes(s));

    if (filteredStates.length === 0) {
      const emptyResult = {
        from, to, from_state: fromState, to_state: toState,
        distance_miles: distanceMiles, distance_source: distanceSource,
        duration_hours: durationHours,
        total: 0, message: 'No toll roads found on this route', breakdown: [],
      };
      cache.set(cacheKey, emptyResult);
      return res.status(200).json(emptyResult);
    }

    const result = calculateTollCost(filteredStates, distanceMiles, truckType, stateMilesMap);
    const response = {
      from, to, from_state: fromState, to_state: toState,
      distance_miles: distanceMiles,
      distance_source: distanceSource, // 'osrm' | 'table' | 'estimated'
      duration_hours: durationHours,   // null если не получили от OSRM
      ...result,
    };

    cache.set(cacheKey, response);

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
}

/**
 * GET /api/tolls/route?from=Dallas,TX&to=Houston,TX&truck_type=5-axle
 * Удобный эндпоинт — принимает города, возвращает расчёт
 */
router.get('/route', (req, res) => {
  return handleRoute(req.query, req.headers, res, db, cache);
});

/**
 * POST /api/tolls/route
 * Body: { from: "Dallas,TX", to: "Houston,TX", truck_type: "2-axle" }
 */
router.post('/route', (req, res) => {
  return handleRoute(req.body, req.headers, res, db, cache);
});


/**
 * POST /api/tolls/calculate
 * Рассчитать стоимость толлов
 * Body: { states: ['TX', 'LA'], distance_miles: 500, truck_type: '5-axle' }
 */
router.post('/calculate', verifyToken, (req, res) => {
  try {
    const { states, distance_miles, origin = '', destination = '' } = req.body;
    // Normalize truck_type: accept both "2axle" and "2-axle" formats → always output "N-axle"
    const normalizeTT = (t) => {
      if (!t) return '2-axle';
      return t.replace(/^(\d)(-?)axle$/, '$1-axle');
    };
    const truck_type = normalizeTT(req.body.truck_type);

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
  // Статичные данные — кешируем на 1 день
  res.set('Cache-Control', 'public, max-age=86400');
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

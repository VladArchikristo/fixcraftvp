/**
 * geoService.js — Точный расчёт маршрута через Nominatim + OSRM
 * Nominatim: OSM геокодинг (бесплатно, без API ключа)
 * OSRM: реальные расстояния по дорогам (бесплатно, без API ключа)
 */

const https = require('https');

// Кэш геокодирования (in-memory, на время работы сервера)
const geocodeCache = new Map();
const routeCache = new Map();
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 часа

/**
 * Выполняет HTTPS GET запрос, возвращает JSON
 */
function httpsGet(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: {
        'User-Agent': 'TollNavigator/1.0 (truck toll calculator)',
        'Accept': 'application/json',
        ...headers,
      },
      timeout: 8000,
    };
    https.get(url, options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`JSON parse error for URL: ${url}`));
        }
      });
    }).on('error', reject).on('timeout', () => reject(new Error('Request timeout')));
  });
}

/**
 * Геокодирует название города в координаты через Nominatim (OpenStreetMap)
 * @param {string} cityQuery — например "Dallas,TX" или "Houston, Texas"
 * @returns {{ lat: number, lon: number, display_name: string } | null}
 */
async function geocodeCity(cityQuery) {
  const cacheKey = cityQuery.toLowerCase().trim();
  const cached = geocodeCache.get(cacheKey);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data;

  try {
    const encoded = encodeURIComponent(cityQuery + ', USA');
    const url = `https://nominatim.openstreetmap.org/search?q=${encoded}&format=json&limit=1&countrycodes=us&addressdetails=1`;

    const results = await httpsGet(url);
    if (!results || results.length === 0) {
      geocodeCache.set(cacheKey, { data: null, ts: Date.now() });
      return null;
    }

    const r = results[0];
    const data = {
      lat: parseFloat(r.lat),
      lon: parseFloat(r.lon),
      display_name: r.display_name,
      state: r.address?.state_code?.toUpperCase() ||
             r.address?.['ISO3166-2-lvl4']?.replace('US-', '').toUpperCase() ||
             null,
    };
    geocodeCache.set(cacheKey, { data, ts: Date.now() });
    return data;
  } catch (err) {
    console.warn('[geoService] geocodeCity error:', err.message);
    return null;
  }
}

/**
 * Haversine формула — расстояние между двумя координатами в милях
 */
function haversineDistance(p1, p2) {
  const R = 3958.8; // радиус Земли в милях
  const dLat = (p2.lat - p1.lat) * Math.PI / 180;
  const dLon = (p2.lon - p1.lon) * Math.PI / 180;
  const lat1 = p1.lat * Math.PI / 180;
  const lat2 = p2.lat * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Получает реальный маршрут через OSRM с полной геометрией (GeoJSON)
 * overview=full&geometries=geojson — возвращает все точки реального пути
 * @param {{ lat, lon }} fromCoords
 * @param {{ lat, lon }} toCoords
 * @returns {{ distanceMiles, durationHours, source, waypoints } | null}
 */
// Список OSRM-серверов (основной + резервные)
const OSRM_SERVERS = [
  'https://router.project-osrm.org',
  'https://routing.openstreetmap.de/routed-car',
];

async function getOSRMRoute(fromCoords, toCoords) {
  for (const server of OSRM_SERVERS) {
    try {
      // overview=full + geometries=geojson — получаем реальную геометрию маршрута
      const url = `${server}/route/v1/driving/${fromCoords.lon},${fromCoords.lat};${toCoords.lon},${toCoords.lat}?overview=full&geometries=geojson&steps=false`;

      const result = await httpsGet(url);

      if (!result || result.code !== 'Ok' || !result.routes || result.routes.length === 0) {
        console.warn(`[geoService] OSRM ${server}: bad response (code=${result?.code})`);
        continue;
      }

      const route = result.routes[0];
      const distanceMeters = route.distance;
      const durationSeconds = route.duration;

      // Извлекаем waypoints из GeoJSON геометрии (реальный путь по дорогам)
      let waypoints = null;
      if (route.geometry && route.geometry.coordinates && route.geometry.coordinates.length > 1) {
        // GeoJSON: [lon, lat] → конвертируем в { lat, lon }
        waypoints = route.geometry.coordinates.map(([lon, lat]) => ({ lat, lon }));
        console.log(`[geoService] OSRM (${server}): ${waypoints.length} waypoints for route`);
      }

      return {
        distanceMiles: Math.round(distanceMeters * 0.000621371),
        durationHours: Math.round(durationSeconds / 360) / 10, // 1 decimal
        source: 'osrm',
        waypoints, // реальные точки маршрута по дорогам
      };
    } catch (err) {
      console.warn(`[geoService] OSRM ${server} error:`, err.message);
      // Попробуем следующий сервер
    }
  }
  console.warn('[geoService] All OSRM servers failed — using hardcoded fallback tables');
  return null;
}

/**
 * Рассчитывает точное распределение миль по штатам на основе реальных waypoints OSRM
 * @param {Array<{lat, lon}>} waypoints — точки маршрута от OSRM
 * @param {number} totalMiles — общее расстояние маршрута
 * @param {Object} stateBounds — bounding boxes штатов
 * @returns {Object|null} — { TX: 400, LA: 115, ... } или null
 */
function calculateStateMilesFromWaypoints(waypoints, totalMiles, stateBounds) {
  if (!waypoints || waypoints.length < 2) return null;

  // Вычисляем длину каждого сегмента через haversine
  const segmentDists = [];
  let totalSegmentDist = 0;
  for (let i = 1; i < waypoints.length; i++) {
    const d = haversineDistance(waypoints[i - 1], waypoints[i]);
    segmentDists.push(d);
    totalSegmentDist += d;
  }

  if (totalSegmentDist === 0) return null;

  // Для каждого сегмента — определяем штат по средней точке, накапливаем мили
  const stateMiles = {};
  for (let i = 1; i < waypoints.length; i++) {
    const midPoint = {
      lat: (waypoints[i - 1].lat + waypoints[i].lat) / 2,
      lon: (waypoints[i - 1].lon + waypoints[i].lon) / 2,
    };

    // Масштабируем реальные OSRM мили пропорционально сегменту
    const segmentMiles = (segmentDists[i - 1] / totalSegmentDist) * totalMiles;

    // Находим штат по bounding box
    let foundState = null;
    for (const [state, bounds] of Object.entries(stateBounds)) {
      if (midPoint.lat >= bounds.minLat && midPoint.lat <= bounds.maxLat &&
          midPoint.lon >= bounds.minLon && midPoint.lon <= bounds.maxLon) {
        foundState = state;
        break;
      }
    }

    if (foundState) {
      stateMiles[foundState] = (stateMiles[foundState] || 0) + segmentMiles;
    }
  }

  // Округляем до целых миль
  for (const state of Object.keys(stateMiles)) {
    stateMiles[state] = Math.round(stateMiles[state]);
  }

  console.log('[geoService] State miles from waypoints:', stateMiles);
  return stateMiles;
}

/**
 * Главная функция — получает точное расстояние между двумя городами
 * Сначала пробует OSRM, при ошибке — возвращает null (будет fallback на таблицы)
 * @param {string} fromCity — "Dallas,TX"
 * @param {string} toCity — "Houston,TX"
 * @returns {{ distanceMiles: number, durationHours: number, source: string } | null}
 */
async function getRealRoute(fromCity, toCity) {
  const cacheKey = `${fromCity.toLowerCase()}|${toCity.toLowerCase()}`;
  const cached = routeCache.get(cacheKey);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data;

  try {
    // Параллельно геокодируем оба города
    const [fromCoords, toCoords] = await Promise.all([
      geocodeCity(fromCity),
      geocodeCity(toCity),
    ]);

    if (!fromCoords || !toCoords) {
      console.warn(`[geoService] Geocoding failed: from="${fromCity}" to="${toCity}"`);
      return null;
    }

    const route = await getOSRMRoute(fromCoords, toCoords);
    if (!route) return null;

    const data = {
      ...route,
      fromCoords,
      toCoords,
    };
    routeCache.set(cacheKey, { data, ts: Date.now() });
    // Кэшируем и обратный маршрут (расстояние одинаковое)
    const reverseKey = `${toCity.toLowerCase()}|${fromCity.toLowerCase()}`;
    routeCache.set(reverseKey, { data, ts: Date.now() });

    return data;
  } catch (err) {
    console.warn('[geoService] getRealRoute error:', err.message);
    return null;
  }
}

/**
 * Определяет американские штаты вдоль маршрута
 * Если переданы waypoints (от OSRM) — использует реальный путь по дорогам.
 * Иначе — линейная интерполяция между точками (менее точно).
 * @param {{ lat, lon }} fromCoords
 * @param {{ lat, lon }} toCoords
 * @param {Array<{lat, lon}>|null} waypoints — реальные точки маршрута от OSRM
 * @returns {{ states: string[], stateMiles: Object|null }}
 */
function getStatesAlongRoute(fromCoords, toCoords, waypoints = null) {
  // Bounding boxes US штатов (приблизительные, для определения коридора)
  const STATE_BOUNDS = {
    'AL': { minLat: 30.1, maxLat: 35.0, minLon: -88.5, maxLon: -84.9 },
    'AR': { minLat: 33.0, maxLat: 36.5, minLon: -94.6, maxLon: -89.6 },
    'AZ': { minLat: 31.3, maxLat: 37.0, minLon: -114.8, maxLon: -109.0 },
    'CA': { minLat: 32.5, maxLat: 42.0, minLon: -124.4, maxLon: -114.1 },
    'CO': { minLat: 37.0, maxLat: 41.0, minLon: -109.1, maxLon: -102.0 },
    'CT': { minLat: 40.9, maxLat: 42.1, minLon: -73.7, maxLon: -71.8 },
    'DE': { minLat: 38.4, maxLat: 39.8, minLon: -75.8, maxLon: -75.0 },
    'FL': { minLat: 24.4, maxLat: 31.0, minLon: -87.6, maxLon: -79.9 },
    'GA': { minLat: 30.4, maxLat: 35.0, minLon: -85.6, maxLon: -80.8 },
    'IA': { minLat: 40.4, maxLat: 43.5, minLon: -96.6, maxLon: -90.1 },
    'ID': { minLat: 41.9, maxLat: 49.0, minLon: -117.2, maxLon: -111.0 },
    'IL': { minLat: 36.9, maxLat: 42.5, minLon: -91.5, maxLon: -87.0 },
    'IN': { minLat: 37.8, maxLat: 41.8, minLon: -88.1, maxLon: -84.8 },
    'KS': { minLat: 37.0, maxLat: 40.0, minLon: -102.1, maxLon: -94.6 },
    'KY': { minLat: 36.5, maxLat: 39.1, minLon: -89.6, maxLon: -81.9 },
    'LA': { minLat: 28.9, maxLat: 33.0, minLon: -94.0, maxLon: -88.8 },
    'MA': { minLat: 41.2, maxLat: 42.9, minLon: -73.5, maxLon: -69.9 },
    'MD': { minLat: 37.9, maxLat: 39.7, minLon: -79.5, maxLon: -75.0 },
    'MI': { minLat: 41.7, maxLat: 48.3, minLon: -90.4, maxLon: -82.4 },
    'MN': { minLat: 43.5, maxLat: 49.4, minLon: -97.2, maxLon: -89.5 },
    'MO': { minLat: 35.9, maxLat: 40.6, minLon: -95.8, maxLon: -89.1 },
    'MS': { minLat: 30.2, maxLat: 35.0, minLon: -91.7, maxLon: -88.1 },
    'MT': { minLat: 44.4, maxLat: 49.0, minLon: -116.0, maxLon: -104.0 },
    'NC': { minLat: 33.8, maxLat: 36.6, minLon: -84.3, maxLon: -75.5 },
    'NE': { minLat: 40.0, maxLat: 43.0, minLon: -104.1, maxLon: -95.3 },
    'NJ': { minLat: 38.9, maxLat: 41.4, minLon: -75.6, maxLon: -73.9 },
    'NM': { minLat: 31.3, maxLat: 37.0, minLon: -109.1, maxLon: -103.0 },
    'NV': { minLat: 35.0, maxLat: 42.0, minLon: -120.0, maxLon: -114.0 },
    'NY': { minLat: 40.5, maxLat: 45.0, minLon: -79.8, maxLon: -71.9 },
    'OH': { minLat: 38.4, maxLat: 42.3, minLon: -84.8, maxLon: -80.5 },
    'OK': { minLat: 33.6, maxLat: 37.0, minLon: -103.0, maxLon: -94.4 },
    'OR': { minLat: 41.9, maxLat: 46.3, minLon: -124.6, maxLon: -116.5 },
    'PA': { minLat: 39.7, maxLat: 42.3, minLon: -80.5, maxLon: -74.7 },
    'RI': { minLat: 41.1, maxLat: 42.0, minLon: -71.9, maxLon: -71.1 },
    'SC': { minLat: 32.0, maxLat: 35.2, minLon: -83.4, maxLon: -78.5 },
    'TN': { minLat: 34.9, maxLat: 36.7, minLon: -90.3, maxLon: -81.6 },
    'TX': { minLat: 25.8, maxLat: 36.5, minLon: -106.6, maxLon: -93.5 },
    'UT': { minLat: 37.0, maxLat: 42.0, minLon: -114.1, maxLon: -109.0 },
    'VA': { minLat: 36.5, maxLat: 39.5, minLon: -83.7, maxLon: -75.2 },
    'WA': { minLat: 45.5, maxLat: 49.0, minLon: -124.8, maxLon: -116.9 },
    'WI': { minLat: 42.5, maxLat: 47.1, minLon: -92.9, maxLon: -86.2 },
    'WV': { minLat: 37.2, maxLat: 40.6, minLon: -82.6, maxLon: -77.7 },
  };

  const statesOnRoute = new Set();

  if (waypoints && waypoints.length > 1) {
    // Используем реальные точки OSRM — максимальная точность
    for (const point of waypoints) {
      for (const [state, bounds] of Object.entries(STATE_BOUNDS)) {
        if (point.lat >= bounds.minLat && point.lat <= bounds.maxLat &&
            point.lon >= bounds.minLon && point.lon <= bounds.maxLon) {
          statesOnRoute.add(state);
        }
      }
    }
    const states = [...statesOnRoute];
    // Считаем точные мили по штатам из waypoints (нужен totalMiles — передадим null, рассчитается позже)
    return { states, stateMiles: null, waypoints };
  } else {
    // Fallback: линейная интерполяция — 30 точек по прямой линии
    const STEPS = 30;
    for (let i = 0; i <= STEPS; i++) {
      const t = i / STEPS;
      const lat = fromCoords.lat + (toCoords.lat - fromCoords.lat) * t;
      const lon = fromCoords.lon + (toCoords.lon - fromCoords.lon) * t;

      for (const [state, bounds] of Object.entries(STATE_BOUNDS)) {
        if (lat >= bounds.minLat && lat <= bounds.maxLat &&
            lon >= bounds.minLon && lon <= bounds.maxLon) {
          statesOnRoute.add(state);
        }
      }
    }
    return { states: [...statesOnRoute], stateMiles: null, waypoints: null };
  }
}

/**
 * Экспортируем STATE_BOUNDS для использования в calculateStateMilesFromWaypoints
 */
function getStateBounds() {
  return {
    'AL': { minLat: 30.1, maxLat: 35.0, minLon: -88.5, maxLon: -84.9 },
    'AR': { minLat: 33.0, maxLat: 36.5, minLon: -94.6, maxLon: -89.6 },
    'AZ': { minLat: 31.3, maxLat: 37.0, minLon: -114.8, maxLon: -109.0 },
    'CA': { minLat: 32.5, maxLat: 42.0, minLon: -124.4, maxLon: -114.1 },
    'CO': { minLat: 37.0, maxLat: 41.0, minLon: -109.1, maxLon: -102.0 },
    'CT': { minLat: 40.9, maxLat: 42.1, minLon: -73.7, maxLon: -71.8 },
    'DE': { minLat: 38.4, maxLat: 39.8, minLon: -75.8, maxLon: -75.0 },
    'FL': { minLat: 24.4, maxLat: 31.0, minLon: -87.6, maxLon: -79.9 },
    'GA': { minLat: 30.4, maxLat: 35.0, minLon: -85.6, maxLon: -80.8 },
    'IA': { minLat: 40.4, maxLat: 43.5, minLon: -96.6, maxLon: -90.1 },
    'ID': { minLat: 41.9, maxLat: 49.0, minLon: -117.2, maxLon: -111.0 },
    'IL': { minLat: 36.9, maxLat: 42.5, minLon: -91.5, maxLon: -87.0 },
    'IN': { minLat: 37.8, maxLat: 41.8, minLon: -88.1, maxLon: -84.8 },
    'KS': { minLat: 37.0, maxLat: 40.0, minLon: -102.1, maxLon: -94.6 },
    'KY': { minLat: 36.5, maxLat: 39.1, minLon: -89.6, maxLon: -81.9 },
    'LA': { minLat: 28.9, maxLat: 33.0, minLon: -94.0, maxLon: -88.8 },
    'MA': { minLat: 41.2, maxLat: 42.9, minLon: -73.5, maxLon: -69.9 },
    'MD': { minLat: 37.9, maxLat: 39.7, minLon: -79.5, maxLon: -75.0 },
    'MI': { minLat: 41.7, maxLat: 48.3, minLon: -90.4, maxLon: -82.4 },
    'MN': { minLat: 43.5, maxLat: 49.4, minLon: -97.2, maxLon: -89.5 },
    'MO': { minLat: 35.9, maxLat: 40.6, minLon: -95.8, maxLon: -89.1 },
    'MS': { minLat: 30.2, maxLat: 35.0, minLon: -91.7, maxLon: -88.1 },
    'MT': { minLat: 44.4, maxLat: 49.0, minLon: -116.0, maxLon: -104.0 },
    'NC': { minLat: 33.8, maxLat: 36.6, minLon: -84.3, maxLon: -75.5 },
    'NE': { minLat: 40.0, maxLat: 43.0, minLon: -104.1, maxLon: -95.3 },
    'NJ': { minLat: 38.9, maxLat: 41.4, minLon: -75.6, maxLon: -73.9 },
    'NM': { minLat: 31.3, maxLat: 37.0, minLon: -109.1, maxLon: -103.0 },
    'NV': { minLat: 35.0, maxLat: 42.0, minLon: -120.0, maxLon: -114.0 },
    'NY': { minLat: 40.5, maxLat: 45.0, minLon: -79.8, maxLon: -71.9 },
    'OH': { minLat: 38.4, maxLat: 42.3, minLon: -84.8, maxLon: -80.5 },
    'OK': { minLat: 33.6, maxLat: 37.0, minLon: -103.0, maxLon: -94.4 },
    'OR': { minLat: 41.9, maxLat: 46.3, minLon: -124.6, maxLon: -116.5 },
    'PA': { minLat: 39.7, maxLat: 42.3, minLon: -80.5, maxLon: -74.7 },
    'RI': { minLat: 41.1, maxLat: 42.0, minLon: -71.9, maxLon: -71.1 },
    'SC': { minLat: 32.0, maxLat: 35.2, minLon: -83.4, maxLon: -78.5 },
    'TN': { minLat: 34.9, maxLat: 36.7, minLon: -90.3, maxLon: -81.6 },
    'TX': { minLat: 25.8, maxLat: 36.5, minLon: -106.6, maxLon: -93.5 },
    'UT': { minLat: 37.0, maxLat: 42.0, minLon: -114.1, maxLon: -109.0 },
    'VA': { minLat: 36.5, maxLat: 39.5, minLon: -83.7, maxLon: -75.2 },
    'WA': { minLat: 45.5, maxLat: 49.0, minLon: -124.8, maxLon: -116.9 },
    'WI': { minLat: 42.5, maxLat: 47.1, minLon: -92.9, maxLon: -86.2 },
    'WV': { minLat: 37.2, maxLat: 40.6, minLon: -82.6, maxLon: -77.7 },
  };
}

module.exports = { getRealRoute, geocodeCity, getStatesAlongRoute, calculateStateMilesFromWaypoints, getStateBounds };

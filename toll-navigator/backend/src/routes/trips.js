const express = require('express');
const db = require('../db');
const { verifyToken } = require('../middleware/auth');

const router = express.Router();

// Ставки IFTA ($ per gallon, 2026) — используем реальные актуальные значения
const IFTA_RATES = {
  TX: 0.20, OK: 0.16, KS: 0.26, MO: 0.17, IL: 0.455,
  IN: 0.33, OH: 0.28, PA: 0.741, NY: 0.398, NJ: 0.175,
  VA: 0.162, NC: 0.361, TN: 0.17, GA: 0.326, FL: 0.359,
  AL: 0.19, MS: 0.18, AR: 0.225, LA: 0.20, CA: 0.824,
  AZ: 0.26, NV: 0.27, UT: 0.249, CO: 0.205, NM: 0.21,
  WY: 0.24, MT: 0.2775, ID: 0.32, WA: 0.494, OR: 0.34,
  // Дополнительные штаты
  AK: 0.0895, CT: 0.401, DE: 0.220, IA: 0.325, KY: 0.216,
  ME: 0.319, MD: 0.358, MA: 0.240, MI: 0.470, MN: 0.285,
  NE: 0.278, NH: 0.222, ND: 0.230, RI: 0.340, SC: 0.220,
  SD: 0.280, VT: 0.320, WV: 0.358, WI: 0.329,
};

// Вспомогательная функция: определяем квартал по дате
function getQuarterYear(date = new Date()) {
  const month = date.getMonth() + 1; // 1-12
  const quarter = Math.ceil(month / 3);
  return { quarter, year: date.getFullYear() };
}

// POST /api/trips — сохранить маршрут после расчёта
router.post('/', verifyToken, (req, res) => {
  try {
    const {
      from_city,
      to_city,
      truck_type = '5-axle',
      total_miles = 0,
      state_miles = {},
      toll_cost = 0,
      fuel_cost = 0,
      mpg = 6.5,
      fuel_purchases = [],
    } = req.body;

    if (!from_city || !to_city) {
      return res.status(400).json({ error: 'from_city and to_city are required' });
    }

    const { quarter, year } = getQuarterYear();
    const stateMilesJson = typeof state_miles === 'string' ? state_miles : JSON.stringify(state_miles);

    // Сохраняем в транзакции
    const insertTrip = db.prepare(`
      INSERT INTO trips (user_id, from_city, to_city, truck_type, total_miles, state_miles, toll_cost, fuel_cost, mpg, quarter, year)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertFuel = db.prepare(`
      INSERT INTO fuel_purchases (user_id, trip_id, state, gallons, price_per_gallon, station_name, quarter, year)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    let tripId;
    // node:sqlite использует синхронный API — оборачиваем транзакцией
    db.exec('BEGIN');
    try {
      const tripResult = insertTrip.run(
        req.userId, from_city, to_city, truck_type,
        total_miles, stateMilesJson, toll_cost, fuel_cost, mpg,
        quarter, year
      );
      tripId = tripResult.lastInsertRowid;

      if (Array.isArray(fuel_purchases) && fuel_purchases.length > 0) {
        for (const fp of fuel_purchases) {
          if (!fp.state || !fp.gallons) continue;
          insertFuel.run(
            req.userId, tripId, fp.state,
            parseFloat(fp.gallons) || 0,
            parseFloat(fp.price_per_gallon) || 0,
            fp.station_name || null,
            quarter, year
          );
        }
      }

      db.exec('COMMIT');
    } catch (txErr) {
      db.exec('ROLLBACK');
      throw txErr;
    }

    res.status(201).json({
      id: tripId,
      from_city,
      to_city,
      quarter,
      year,
      message: 'Trip saved successfully',
    });
  } catch (err) {
    console.error('POST /api/trips error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/trips/ifta?quarter=2&year=2026 — IFTA расчёт за квартал
router.get('/ifta', verifyToken, (req, res) => {
  try {
    const { quarter, year } = getQuarterYear();
    const q = parseInt(req.query.quarter) || quarter;
    const y = parseInt(req.query.year) || year;

    // Все поездки за квартал
    const trips = db.prepare(`
      SELECT id, state_miles, total_miles, mpg
      FROM trips
      WHERE user_id = ? AND quarter = ? AND year = ?
    `).all(req.userId, q, y);

    // Все заправки за квартал
    const fuels = db.prepare(`
      SELECT state, SUM(gallons) as purchased_gallons
      FROM fuel_purchases
      WHERE user_id = ? AND quarter = ? AND year = ?
      GROUP BY state
    `).all(req.userId, q, y);

    // Индекс купленных галлонов по штату
    const purchasedByState = {};
    fuels.forEach(f => {
      purchasedByState[f.state] = (purchasedByState[f.state] || 0) + f.purchased_gallons;
    });

    // Агрегируем мили по штатам из всех поездок
    const milesByState = {};
    let totalMilesAll = 0;
    let totalMpgSum = 0;
    let mpgCount = 0;

    trips.forEach(trip => {
      let stateMiles = {};
      try {
        stateMiles = JSON.parse(trip.state_miles || '{}');
      } catch (_) {}

      totalMilesAll += trip.total_miles || 0;
      if (trip.mpg && trip.mpg > 0) {
        totalMpgSum += trip.mpg;
        mpgCount++;
      }

      Object.entries(stateMiles).forEach(([state, miles]) => {
        milesByState[state] = (milesByState[state] || 0) + parseFloat(miles || 0);
      });
    });

    const avgMpg = mpgCount > 0 ? totalMpgSum / mpgCount : 6.5;

    // Считаем IFTA по каждому штату
    const states = Object.entries(milesByState).map(([state, total_miles_state]) => {
      const consumed_gallons = total_miles_state / avgMpg;
      const purchased_gallons = purchasedByState[state] || 0;
      const net_gallons = consumed_gallons - purchased_gallons;
      const tax_rate = IFTA_RATES[state] || 0;
      const tax_due = net_gallons * tax_rate;

      return {
        state,
        total_miles: parseFloat(total_miles_state.toFixed(2)),
        consumed_gallons: parseFloat(consumed_gallons.toFixed(3)),
        purchased_gallons: parseFloat(purchased_gallons.toFixed(3)),
        net_gallons: parseFloat(net_gallons.toFixed(3)),
        tax_rate,
        tax_due: parseFloat(tax_due.toFixed(4)),
        refund: tax_due < 0, // true = переплата, возврат
      };
    }).sort((a, b) => a.state.localeCompare(b.state));

    const total_tax_due = states.reduce((sum, s) => sum + s.tax_due, 0);

    res.json({
      quarter: q,
      year: y,
      total_trips: trips.length,
      total_miles: parseFloat(totalMilesAll.toFixed(2)),
      avg_mpg: parseFloat(avgMpg.toFixed(2)),
      states,
      total_tax_due: parseFloat(total_tax_due.toFixed(4)),
    });
  } catch (err) {
    console.error('GET /api/trips/ifta error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/trips/history — история всех поездок пользователя
router.get('/history', verifyToken, (req, res) => {
  try {
    const trips = db.prepare(`
      SELECT t.*,
        (SELECT json_group_array(json_object(
          'id', fp.id,
          'state', fp.state,
          'gallons', fp.gallons,
          'price_per_gallon', fp.price_per_gallon,
          'station_name', fp.station_name,
          'purchase_date', fp.purchase_date
        ))
        FROM fuel_purchases fp WHERE fp.trip_id = t.id) as fuel_purchases
      FROM trips t
      WHERE t.user_id = ?
      ORDER BY t.created_at DESC
    `).all(req.userId);

    // Парсим JSON поля
    const result = trips.map(trip => ({
      ...trip,
      state_miles: (() => { try { return JSON.parse(trip.state_miles || '{}'); } catch (_) { return {}; } })(),
      fuel_purchases: (() => { try { return JSON.parse(trip.fuel_purchases || '[]'); } catch (_) { return []; } })(),
    }));

    res.json({ trips: result, total: result.length });
  } catch (err) {
    console.error('GET /api/trips/history error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/trips/fuel-purchases?quarter=2&year=2026 — заправки за квартал
router.get('/fuel-purchases', verifyToken, (req, res) => {
  try {
    const { quarter, year } = getQuarterYear();
    const q = parseInt(req.query.quarter) || quarter;
    const y = parseInt(req.query.year) || year;

    const purchases = db.prepare(`
      SELECT fp.*, t.from_city, t.to_city
      FROM fuel_purchases fp
      LEFT JOIN trips t ON t.id = fp.trip_id
      WHERE fp.user_id = ? AND fp.quarter = ? AND fp.year = ?
      ORDER BY fp.purchase_date DESC
    `).all(req.userId, q, y);

    const totalGallons = purchases.reduce((sum, p) => sum + (p.gallons || 0), 0);
    const totalCost = purchases.reduce((sum, p) => sum + ((p.gallons || 0) * (p.price_per_gallon || 0)), 0);

    res.json({
      quarter: q,
      year: y,
      purchases,
      total_gallons: parseFloat(totalGallons.toFixed(3)),
      total_cost: parseFloat(totalCost.toFixed(2)),
    });
  } catch (err) {
    console.error('GET /api/trips/fuel-purchases error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/trips/scan-receipt — OCR скан чека заправки
router.post('/scan-receipt', verifyToken, async (req, res) => {
  try {
    const { image_base64 } = req.body;
    if (!image_base64) {
      return res.status(400).json({ error: 'image_base64 is required' });
    }

    const apiKey = process.env.GOOGLE_VISION_API_KEY;

    // Если нет ключа — возвращаем mock-данные для разработки
    if (!apiKey) {
      console.log('[scan-receipt] No GOOGLE_VISION_API_KEY — returning mock data');
      return res.json({
        state: 'TX',
        gallons: 85.4,
        price_per_gallon: 3.89,
        date: new Date().toISOString().split('T')[0],
        station_name: 'Pilot Travel Center',
        raw_text: 'mock',
        mock: true,
      });
    }

    // Google Vision API — text detection
    const visionRes = await fetch(
      `https://vision.googleapis.com/v1/images:annotate?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requests: [{
            image: { content: image_base64 },
            features: [{ type: 'TEXT_DETECTION', maxResults: 1 }],
          }],
        }),
      }
    );

    if (!visionRes.ok) {
      const errText = await visionRes.text();
      console.error('[scan-receipt] Vision API error:', errText);
      return res.status(502).json({ error: 'Google Vision API error', details: errText });
    }

    const visionData = await visionRes.json();
    const rawText = visionData.responses?.[0]?.fullTextAnnotation?.text || '';

    // Парсим текст чека
    const parsed = parseReceiptText(rawText);

    res.json({ ...parsed, raw_text: rawText });
  } catch (err) {
    console.error('POST /api/trips/scan-receipt error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// Парсим текст чека — извлекаем ключевые данные
function parseReceiptText(text) {
  const result = {
    state: null,
    gallons: null,
    price_per_gallon: null,
    date: null,
    station_name: null,
  };

  if (!text) return result;

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

  // Название станции — первые строки обычно
  const stationKeywords = ['pilot', 'loves', 'flying j', 'petro', 'ta travel', 'speedway', 'kwik trip', 'casey', 'circle k', 'shell', 'bp', 'marathon', 'chevron'];
  for (const line of lines.slice(0, 5)) {
    if (stationKeywords.some(k => line.toLowerCase().includes(k))) {
      result.station_name = line;
      break;
    }
  }

  // Штат — ищем аббревиатуру USA штата (2 буквы)
  const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'];
  for (const line of lines) {
    const match = line.match(/\b([A-Z]{2})\b/);
    if (match && US_STATES.includes(match[1])) {
      result.state = match[1];
      break;
    }
  }

  // Галлоны — ищем паттерн "XX.X GAL" или "GALLONS XX.X"
  for (const line of lines) {
    const galMatch = line.match(/(\d+\.\d+)\s*(?:gal|gallons|GAL|GALLONS)/i)
      || line.match(/(?:gal|gallons)\s*(\d+\.\d+)/i);
    if (galMatch) {
      result.gallons = parseFloat(galMatch[1]);
      break;
    }
  }

  // Цена за галлон — ищем паттерн "$X.XXX/GAL" или "PRICE/GAL X.XXX"
  for (const line of lines) {
    const priceMatch = line.match(/\$?(\d+\.\d{2,3})\s*\/\s*(?:gal|gallon)/i)
      || line.match(/(?:price|per gal)[^\d]*(\d+\.\d{2,3})/i);
    if (priceMatch) {
      result.price_per_gallon = parseFloat(priceMatch[1]);
      break;
    }
  }

  // Дата — ищем паттерн MM/DD/YYYY или YYYY-MM-DD
  for (const line of lines) {
    const dateMatch = line.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/)
      || line.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (dateMatch) {
      // Нормализуем в YYYY-MM-DD
      if (dateMatch[0].includes('-')) {
        result.date = dateMatch[0];
      } else {
        const [, m, d, y] = dateMatch;
        result.date = `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
      }
      break;
    }
  }

  // Если дата не найдена — сегодняшняя
  if (!result.date) {
    result.date = new Date().toISOString().split('T')[0];
  }

  return result;
}

// POST /api/trips/fuel-purchases — добавить заправку вручную
router.post('/fuel-purchases', verifyToken, (req, res) => {
  try {
    const {
      state,
      gallons,
      price_per_gallon = 0,
      station_name = null,
      trip_id = null,
      purchase_date = null,
    } = req.body;

    if (!state || !gallons) {
      return res.status(400).json({ error: 'state and gallons are required' });
    }

    const { quarter, year } = getQuarterYear(purchase_date ? new Date(purchase_date) : new Date());

    const result = db.prepare(`
      INSERT INTO fuel_purchases (user_id, trip_id, state, gallons, price_per_gallon, station_name, quarter, year, purchase_date)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      req.userId,
      trip_id || null,
      state,
      parseFloat(gallons),
      parseFloat(price_per_gallon) || 0,
      station_name,
      quarter,
      year,
      purchase_date || new Date().toISOString(),
    );

    res.status(201).json({
      id: result.lastInsertRowid,
      state,
      gallons: parseFloat(gallons),
      price_per_gallon: parseFloat(price_per_gallon) || 0,
      quarter,
      year,
      message: 'Fuel purchase saved',
    });
  } catch (err) {
    console.error('POST /api/trips/fuel-purchases error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

module.exports = router;

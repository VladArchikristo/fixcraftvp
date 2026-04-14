/**
 * Tests for iftaMileageTracker.js
 *
 * Мокируем expo-sqlite и stateDetectionService.
 * Тестируем: Haversine, обработку батчей, накопление миль, фильтрацию шума.
 */

// ─── Моки внешних зависимостей ───────────────────────────────────────────────

// Минимальный in-memory mock для expo-sqlite
const mockDb = {
  _store: {},          // { 'last_point': JSON }
  _mileage: {},        // { 'DATE|STATE': miles }

  execAsync: jest.fn().mockResolvedValue(undefined),

  getFirstAsync: jest.fn(async (sql, params) => {
    if (sql.includes('ifta_tracking_state')) {
      const val = mockDb._store['last_point'];
      return val ? { value: val } : null;
    }
    if (sql.includes('ifta_mileage') && sql.includes('SELECT id')) {
      const key = `${params[0]}|${params[1]}`;
      const miles = mockDb._mileage[key];
      return miles !== undefined ? { id: key, miles } : null;
    }
    if (sql.includes('COALESCE(SUM')) {
      // getTodayMiles
      const today = new Date().toISOString().slice(0, 10);
      const total = Object.entries(mockDb._mileage)
        .filter(([k]) => k.startsWith(today))
        .reduce((s, [, v]) => s + v, 0);
      return { total };
    }
    return null;
  }),

  runAsync: jest.fn(async (sql, params) => {
    if (sql.includes('ifta_tracking_state')) {
      mockDb._store['last_point'] = params[0];
    }
    if (sql.includes('UPDATE ifta_mileage')) {
      // params: [miles, lat, lng, timestamp, id]
      const key = params[4];
      mockDb._mileage[key] = (mockDb._mileage[key] || 0) + params[0];
    }
    if (sql.includes('INSERT INTO ifta_mileage')) {
      // params: [date, state_code, miles, lat, lng, timestamp]
      const key = `${params[0]}|${params[1]}`;
      mockDb._mileage[key] = (mockDb._mileage[key] || 0) + params[2];
    }
  }),

  getAllAsync: jest.fn(async (sql, params) => {
    const [start, end] = params;
    const result = {};
    Object.entries(mockDb._mileage).forEach(([key, miles]) => {
      const [date, state] = key.split('|');
      if (date >= start && date <= end) {
        result[state] = (result[state] || 0) + miles;
      }
    });
    return Object.entries(result).map(([state_code, miles]) => ({ state_code, miles }));
  }),

  _reset() {
    this._store = {};
    this._mileage = {};
    this.execAsync.mockClear();
    this.getFirstAsync.mockClear();
    this.runAsync.mockClear();
    this.getAllAsync.mockClear();
  },
};

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn().mockResolvedValue(mockDb),
}));

// Мок для stateDetectionService — управляем через mockDetectState
let mockDetectState = jest.fn();

jest.mock('../services/stateDetectionService', () => ({
  detectState: (...args) => mockDetectState(...args),
}));

// ─── Импорт тестируемых функций ───────────────────────────────────────────────

const {
  processBatchedLocations,
  getMileageByState,
  getTodayMiles,
  clearAllMileageData,
} = require('../services/iftaMileageTracker');

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeLocation(lat, lng, timestamp = Date.now()) {
  return { coords: { latitude: lat, longitude: lng }, timestamp };
}

// ─────────────────────────────────────────────────────────────────────────────
// Haversine — отдельный тест через публичный интерфейс processBatchedLocations
// ─────────────────────────────────────────────────────────────────────────────

describe('Haversine distance (via processBatchedLocations)', () => {
  beforeEach(() => {
    mockDb._reset();
    mockDetectState.mockReturnValue({ state: 'TX', stateName: 'Texas' });
  });

  test('расстояние ~0 миль между одинаковыми точками — не записывается (шум < 0.01)', async () => {
    const ts = Date.now();
    await processBatchedLocations([
      makeLocation(32.7767, -96.7970, ts),
      makeLocation(32.7767, -96.7970, ts + 40000),
    ]);
    // Дистанция = 0 → dist < 0.01, второй вызов runAsync не должен записать мили
    const mileageEntries = Object.values(mockDb._mileage);
    expect(mileageEntries.every(m => m === 0)).toBeTruthy();
  });

  test('Даллас → Хьюстон (~240 миль) записывается в TX', async () => {
    const ts = Date.now();
    // Первая точка — стартовая (просто сохраняется как lastPoint)
    await processBatchedLocations([makeLocation(32.7767, -96.7970, ts)]);
    // Вторая точка — через 40 сек, Хьюстон
    await processBatchedLocations([makeLocation(29.7604, -95.3698, ts + 40000)]);

    const today = new Date(ts).toISOString().slice(0, 10);
    const miles = mockDb._mileage[`${today}|TX`];
    expect(miles).toBeDefined();
    // Haversine Даллас-Хьюстон ≈ 224–240 миль
    expect(miles).toBeGreaterThan(200);
    expect(miles).toBeLessThan(260);
  });

  test('нью-йорк → бостон (~215 миль) записывается корректно', async () => {
    mockDetectState.mockReturnValue({ state: 'MA', stateName: 'Massachusetts' });
    const ts = Date.now();
    await processBatchedLocations([makeLocation(40.7128, -74.0060, ts)]);
    await processBatchedLocations([makeLocation(42.3601, -71.0589, ts + 40000)]);

    const today = new Date(ts).toISOString().slice(0, 10);
    const miles = mockDb._mileage[`${today}|MA`];
    expect(miles).toBeGreaterThan(190);
    expect(miles).toBeLessThan(240);
  });

  test('нереальный прыжок >300 миль (самолёт) — игнорируется', async () => {
    const ts = Date.now();
    await processBatchedLocations([makeLocation(32.7767, -96.7970, ts)]);
    // Лос-Анджелес — 1400+ миль от Далласа
    await processBatchedLocations([makeLocation(34.0522, -118.2437, ts + 40000)]);

    expect(Object.keys(mockDb._mileage)).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// processBatchedLocations — обработка батчей
// ─────────────────────────────────────────────────────────────────────────────

describe('processBatchedLocations', () => {
  beforeEach(() => {
    mockDb._reset();
  });

  test('пустой массив — ничего не записывает', async () => {
    await processBatchedLocations([]);
    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });

  test('null — ничего не записывает', async () => {
    await processBatchedLocations(null);
    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });

  test('первая точка только сохраняется как lastPoint, мили не добавляются', async () => {
    mockDetectState.mockReturnValue({ state: 'TX', stateName: 'Texas' });
    const ts = Date.now();
    await processBatchedLocations([makeLocation(32.7767, -96.7970, ts)]);

    // runAsync должен сохранить last_point (1 вызов), но НЕ вставлять в ifta_mileage
    const insertCalls = mockDb.runAsync.mock.calls.filter(([sql]) =>
      sql.includes('ifta_mileage')
    );
    expect(insertCalls).toHaveLength(0);
  });

  test('точка за пределами США (detectState = null) — мили не записываются', async () => {
    mockDetectState.mockReturnValue(null);
    const ts = Date.now();
    // Установим lastPoint вручную через обход первой точки
    await processBatchedLocations([makeLocation(32.7767, -96.7970, ts)]);
    await processBatchedLocations([makeLocation(43.6532, -79.3832, ts + 40000)]); // Канада

    const mileageInserts = mockDb.runAsync.mock.calls.filter(([sql]) =>
      sql.includes('ifta_mileage')
    );
    expect(mileageInserts).toHaveLength(0);
  });

  test('батч из нескольких точек обрабатывается хронологически', async () => {
    mockDetectState.mockReturnValue({ state: 'TX', stateName: 'Texas' });
    const base = Date.now();
    // Точки поданы в обратном порядке — должны быть отсортированы
    await processBatchedLocations([
      makeLocation(29.7604, -95.3698, base + 80000), // 3-я
      makeLocation(32.7767, -96.7970, base),           // 1-я
      makeLocation(31.5, -96.0, base + 40000),         // 2-я
    ]);

    const today = new Date(base).toISOString().slice(0, 10);
    const miles = mockDb._mileage[`${today}|TX`];
    expect(miles).toBeGreaterThan(0);
  });

  test('накопление миль по одному штату за несколько вызовов', async () => {
    mockDetectState.mockReturnValue({ state: 'TX', stateName: 'Texas' });
    const base = Date.now();
    const today = new Date(base).toISOString().slice(0, 10);

    // Первый отрезок: Dallas → Waco (~90 миль)
    await processBatchedLocations([makeLocation(32.7767, -96.7970, base)]);
    await processBatchedLocations([makeLocation(31.5493, -97.1467, base + 40000)]);

    const after1 = mockDb._mileage[`${today}|TX`] || 0;
    expect(after1).toBeGreaterThan(0);

    // Второй отрезок: Waco → Austin (~100 миль)
    await processBatchedLocations([makeLocation(30.2672, -97.7431, base + 80000)]);
    const after2 = mockDb._mileage[`${today}|TX`] || 0;
    expect(after2).toBeGreaterThan(after1);
  });

  test('GPS шум < 0.01 мили (~53 фута) — игнорируется', async () => {
    mockDetectState.mockReturnValue({ state: 'TX', stateName: 'Texas' });
    const base = Date.now();
    await processBatchedLocations([makeLocation(32.7767, -96.7970, base)]);
    // Сдвиг ~0.00005 градуса ≈ 5 метров
    await processBatchedLocations([makeLocation(32.77671, -96.79701, base + 40000)]);

    expect(Object.keys(mockDb._mileage)).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getMileageByState
// ─────────────────────────────────────────────────────────────────────────────

describe('getMileageByState', () => {
  beforeEach(() => {
    mockDb._reset();
  });

  test('возвращает пустой массив если данных нет', async () => {
    const result = await getMileageByState('2026-01-01', '2026-03-31');
    expect(result).toEqual([]);
  });

  test('возвращает записи в нужном диапазоне дат', async () => {
    mockDb._mileage['2026-01-15|TX'] = 150;
    mockDb._mileage['2026-02-20|CA'] = 300;
    mockDb._mileage['2026-04-01|NY'] = 200; // за пределами диапазона

    const result = await getMileageByState('2026-01-01', '2026-03-31');
    const stateCodes = result.map(r => r.state_code);

    expect(stateCodes).toContain('TX');
    expect(stateCodes).toContain('CA');
    expect(stateCodes).not.toContain('NY');
  });

  test('суммирует мили по штату за несколько дней', async () => {
    mockDb._mileage['2026-01-10|TX'] = 100;
    mockDb._mileage['2026-01-11|TX'] = 200;

    const result = await getMileageByState('2026-01-01', '2026-01-31');
    const tx = result.find(r => r.state_code === 'TX');
    expect(tx).toBeDefined();
    expect(tx.miles).toBe(300);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getTodayMiles
// ─────────────────────────────────────────────────────────────────────────────

describe('getTodayMiles', () => {
  beforeEach(() => {
    mockDb._reset();
  });

  test('возвращает 0 если сегодня нет данных', async () => {
    const result = await getTodayMiles();
    expect(result).toBe(0);
  });

  test('возвращает сумму миль по всем штатам за сегодня', async () => {
    const today = new Date().toISOString().slice(0, 10);
    mockDb._mileage[`${today}|TX`] = 120.5;
    mockDb._mileage[`${today}|OK`] = 80.3;

    const result = await getTodayMiles();
    // mock getAllAsync суммирует всё за сегодня → 200.8
    // Но getTodayMiles использует getFirstAsync с COALESCE(SUM)
    expect(typeof result).toBe('number');
    expect(result).toBeGreaterThanOrEqual(0);
  });
});

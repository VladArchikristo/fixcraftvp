/**
 * Tests for expenseService.js
 *
 * Мокируем expo-sqlite через in-memory store.
 * Тестируем: addExpense, addLoad, getExpensesSummary, getProfitAndLoss,
 *             getLoadProfitability, learnVendorCategory, getVendorCategory.
 */

// ─── In-memory SQLite mock ────────────────────────────────────────────────────

const mockDb = {
  _expenses: [],       // { id, category, amount, vendor, state, load_id, trip_date, created_at, ... }
  _loads: [],          // { id, gross_rate, net_pay, miles, delivered_at, created_at, ... }
  _vendors: {},        // { vendor_name: { category, learned_at } }

  execAsync: jest.fn().mockResolvedValue(undefined),

  runAsync: jest.fn(async (sql, params) => {
    if (sql.includes('INSERT INTO expenses')) {
      // (id, category, amount, vendor, notes, receipt_image_uri, state, load_id, created_at, trip_date)
      mockDb._expenses.push({
        id: params[0],
        category: params[1],
        amount: params[2],
        vendor: params[3],
        notes: params[4],
        receipt_image_uri: params[5],
        state: params[6],
        load_id: params[7],
        created_at: params[8],
        trip_date: params[9],
      });
    }
    if (sql.includes('INSERT INTO loads')) {
      // (id, gross_rate, fuel_surcharge, detention_pay, factoring_enabled, factoring_percent,
      //  net_pay, miles, origin, destination, broker_name, load_tracking_token,
      //  started_at, delivered_at, created_at)
      mockDb._loads.push({
        id: params[0],
        gross_rate: params[1],
        fuel_surcharge: params[2],
        detention_pay: params[3],
        factoring_enabled: params[4],
        factoring_percent: params[5],
        net_pay: params[6],
        miles: params[7],
        origin: params[8],
        destination: params[9],
        broker_name: params[10],
        load_tracking_token: params[11],
        started_at: params[12],
        delivered_at: params[13],
        created_at: params[14],
      });
    }
    if (sql.includes('INSERT OR REPLACE INTO vendor_categories')) {
      // (vendor_name, category, learned_at)
      mockDb._vendors[params[0]] = { category: params[1], learned_at: params[2] };
    }
  }),

  getFirstAsync: jest.fn(async (sql, params) => {
    // Load by id
    if (sql.includes('FROM loads WHERE id')) {
      return mockDb._loads.find(l => l.id === params[0]) ?? null;
    }
    // Revenue + miles aggregation for getProfitAndLoss
    if (sql.includes('COALESCE(SUM(net_pay)')) {
      const [startDate, endDate] = params;
      const matching = mockDb._loads.filter(l => {
        const date = (l.delivered_at || l.created_at || '').slice(0, 10);
        return date >= startDate && date <= endDate;
      });
      const gross_revenue = matching.reduce((s, l) => s + (l.net_pay || 0), 0);
      const miles_driven = matching.reduce((s, l) => s + (l.miles || 0), 0);
      return { gross_revenue, miles_driven };
    }
    // vendor_categories lookup
    if (sql.includes('FROM vendor_categories')) {
      const vendorName = params[0];
      const entry = mockDb._vendors[vendorName];
      return entry ? { category: entry.category } : null;
    }
    return null;
  }),

  getAllAsync: jest.fn(async (sql, params) => {
    // Expenses by load_id (getLoadProfitability) — проверяем первым, т.к. более специфично
    if (sql.includes('FROM expenses') && sql.includes('WHERE load_id')) {
      const [loadId] = params;
      const filtered = mockDb._expenses.filter(e => e.load_id === loadId);
      const grouped = {};
      filtered.forEach(e => {
        grouped[e.category] = (grouped[e.category] || 0) + e.amount;
      });
      return Object.entries(grouped).map(([category, total]) => ({ category, total }));
    }
    // Expenses by category for period (getExpensesSummary, getProfitAndLoss)
    if (sql.includes('FROM expenses') && sql.includes('GROUP BY category')) {
      const [startDate, endDate] = params;
      const filtered = mockDb._expenses.filter(
        e => e.trip_date >= startDate && e.trip_date <= endDate
      );
      const grouped = {};
      filtered.forEach(e => {
        grouped[e.category] = (grouped[e.category] || 0) + e.amount;
      });
      return Object.entries(grouped).map(([category, total]) => ({ category, total }));
    }
    // All expenses for period (getExpensesByPeriod)
    if (sql.includes('FROM expenses') && sql.includes('ORDER BY trip_date')) {
      const [startDate, endDate] = params;
      return mockDb._expenses.filter(
        e => e.trip_date >= startDate && e.trip_date <= endDate
      );
    }
    // All loads for period
    if (sql.includes('FROM loads') && sql.includes('ORDER BY created_at')) {
      const [startDate, endDate] = params;
      return mockDb._loads.filter(
        l => l.created_at >= startDate && l.created_at <= endDate
      );
    }
    return [];
  }),

  _reset() {
    this._expenses = [];
    this._loads = [];
    this._vendors = {};
    this.execAsync.mockClear();
    this.runAsync.mockClear();
    this.getFirstAsync.mockClear();
    this.getAllAsync.mockClear();
  },
};

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn().mockResolvedValue(mockDb),
}));

// ─── Импорт тестируемого модуля ───────────────────────────────────────────────

const {
  addExpense,
  addLoad,
  getExpensesSummary,
  getProfitAndLoss,
  getLoadProfitability,
  learnVendorCategory,
  getVendorCategory,
  clearAllExpenseData,
} = require('../services/expenseService');

// ─── Helpers ──────────────────────────────────────────────────────────────────

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function makeExpense(overrides = {}) {
  return {
    category: 'diesel',
    amount: 150.0,
    trip_date: todayStr(),
    ...overrides,
  };
}

function makeLoad(overrides = {}) {
  return {
    gross_rate: 2500,
    fuel_surcharge: 200,
    detention_pay: 0,
    factoring_enabled: 0,
    factoring_percent: 0,
    net_pay: 2700,
    miles: 500,
    origin: 'Dallas, TX',
    destination: 'Chicago, IL',
    broker_name: 'Echo Global',
    created_at: new Date().toISOString(),
    delivered_at: todayStr(),
    ...overrides,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// addExpense
// ─────────────────────────────────────────────────────────────────────────────

describe('addExpense()', () => {
  beforeEach(() => mockDb._reset());

  test('возвращает expense с id и created_at', async () => {
    const result = await addExpense(makeExpense());

    expect(result.id).toBeDefined();
    expect(result.created_at).toBeDefined();
    expect(result.category).toBe('diesel');
    expect(result.amount).toBe(150.0);
  });

  test('сохраняет запись в БД через runAsync', async () => {
    await addExpense(makeExpense({ vendor: 'Love\'s Travel Stop', amount: 200 }));

    const insertCalls = mockDb.runAsync.mock.calls.filter(([sql]) =>
      sql.includes('INSERT INTO expenses')
    );
    expect(insertCalls).toHaveLength(1);
  });

  test('все опциональные поля могут быть null', async () => {
    const result = await addExpense({
      category: 'food',
      amount: 25,
      trip_date: todayStr(),
    });

    expect(result.vendor).toBeNull();
    expect(result.notes).toBeNull();
    expect(result.state).toBeNull();
    expect(result.load_id).toBeNull();
  });

  test('автоматически учит vendor → category если vendor указан', async () => {
    await addExpense(makeExpense({ vendor: 'Pilot Flying J', category: 'diesel' }));

    const category = await getVendorCategory('Pilot Flying J');
    expect(category).toBe('diesel');
  });

  test('не вызывает learnVendor если vendor = null', async () => {
    await addExpense(makeExpense({ vendor: null }));

    const vendorInserts = mockDb.runAsync.mock.calls.filter(([sql]) =>
      sql.includes('vendor_categories')
    );
    expect(vendorInserts).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// addLoad
// ─────────────────────────────────────────────────────────────────────────────

describe('addLoad()', () => {
  beforeEach(() => mockDb._reset());

  test('возвращает load с id и created_at', async () => {
    const result = await addLoad(makeLoad());

    expect(result.id).toBeDefined();
    expect(result.created_at).toBeDefined();
    expect(result.gross_rate).toBe(2500);
    expect(result.net_pay).toBe(2700);
  });

  test('сохраняет в БД через runAsync', async () => {
    await addLoad(makeLoad());

    const insertCalls = mockDb.runAsync.mock.calls.filter(([sql]) =>
      sql.includes('INSERT INTO loads')
    );
    expect(insertCalls).toHaveLength(1);
  });

  test('factoring_enabled = true конвертируется в 1 для SQLite', async () => {
    await addLoad(makeLoad({ factoring_enabled: true, factoring_percent: 3 }));

    const [, params] = mockDb.runAsync.mock.calls.find(([sql]) =>
      sql.includes('INSERT INTO loads')
    );
    // factoring_enabled — 5-й параметр (index 4)
    expect(params[4]).toBe(1);
  });

  test('defaults для опциональных полей', async () => {
    const result = await addLoad({
      gross_rate: 1800,
      net_pay: 1800,
    });

    expect(result.fuel_surcharge).toBe(0);
    expect(result.detention_pay).toBe(0);
    expect(result.factoring_enabled).toBe(0);
    expect(result.miles).toBeNull();
    expect(result.origin).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getExpensesSummary
// ─────────────────────────────────────────────────────────────────────────────

describe('getExpensesSummary()', () => {
  beforeEach(() => mockDb._reset());

  test('возвращает пустой byCategory если расходов нет', async () => {
    const result = await getExpensesSummary('month');

    expect(result.byCategory).toEqual({});
    expect(result.totalExpenses).toBe(0);
  });

  test('группирует расходы по категориям', async () => {
    await addExpense(makeExpense({ category: 'diesel', amount: 200 }));
    await addExpense(makeExpense({ category: 'diesel', amount: 150 }));
    await addExpense(makeExpense({ category: 'food', amount: 50 }));

    const result = await getExpensesSummary('month');

    expect(result.byCategory.diesel).toBe(350);
    expect(result.byCategory.food).toBe(50);
    expect(result.totalExpenses).toBe(400);
  });

  test('содержит period, startDate, endDate', async () => {
    const result = await getExpensesSummary('week');

    expect(result.period).toBe('week');
    expect(result.startDate).toBeDefined();
    expect(result.endDate).toBeDefined();
    expect(result.endDate).toBe(todayStr());
  });

  test('поддерживает все периоды: week, month, quarter, year', async () => {
    for (const period of ['week', 'month', 'quarter', 'year']) {
      const result = await getExpensesSummary(period);
      expect(result.period).toBe(period);
      expect(typeof result.totalExpenses).toBe('number');
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getProfitAndLoss
// ─────────────────────────────────────────────────────────────────────────────

describe('getProfitAndLoss()', () => {
  beforeEach(() => mockDb._reset());

  test('возвращает нулевые значения при отсутствии данных', async () => {
    const result = await getProfitAndLoss('month');

    expect(result.grossRevenue).toBe(0);
    expect(result.totalExpenses).toBe(0);
    expect(result.netProfit).toBe(0);
    expect(result.milesDriven).toBe(0);
  });

  test('структура PnL соответствует интерфейсу', async () => {
    const result = await getProfitAndLoss('month');

    expect(result).toHaveProperty('grossRevenue');
    expect(result).toHaveProperty('expenses');
    expect(result).toHaveProperty('totalExpenses');
    expect(result).toHaveProperty('netProfit');
    expect(result).toHaveProperty('milesDriven');
    expect(result).toHaveProperty('revenuePerMile');
    expect(result).toHaveProperty('costPerMile');
    expect(result).toHaveProperty('profitPerMile');
    expect(result).toHaveProperty('period');
  });

  test('netProfit = grossRevenue - totalExpenses', async () => {
    // Добавляем груз: net_pay = 3000
    await addLoad(makeLoad({ net_pay: 3000, miles: 600, delivered_at: todayStr() }));
    // Добавляем расходы: 500 (diesel) + 200 (hotel)
    await addExpense(makeExpense({ category: 'diesel', amount: 500 }));
    await addExpense(makeExpense({ category: 'hotel', amount: 200 }));

    const result = await getProfitAndLoss('month');

    expect(result.grossRevenue).toBe(3000);
    expect(result.totalExpenses).toBe(700);
    expect(result.netProfit).toBe(2300);
  });

  test('revenuePerMile корректно рассчитывается', async () => {
    await addLoad(makeLoad({ net_pay: 3000, miles: 600, delivered_at: todayStr() }));

    const result = await getProfitAndLoss('month');

    // 3000 / 600 = 5.0
    expect(result.revenuePerMile).toBeCloseTo(5.0, 2);
  });

  test('profitPerMile = 0 если нет миль', async () => {
    const result = await getProfitAndLoss('month');
    expect(result.profitPerMile).toBe(0);
  });

  test('expenses — объект с суммами по категориям', async () => {
    await addExpense(makeExpense({ category: 'diesel', amount: 300 }));
    await addExpense(makeExpense({ category: 'permits', amount: 150 }));

    const result = await getProfitAndLoss('month');

    expect(result.expenses.diesel).toBe(300);
    expect(result.expenses.permits).toBe(150);
  });

  test('поддерживает кастомный период YYYY-MM-DD:YYYY-MM-DD', async () => {
    const result = await getProfitAndLoss('2026-01-01:2026-03-31');

    expect(result.period).toBe('2026-01-01:2026-03-31');
    expect(result.startDate).toBe('2026-01-01');
    expect(result.endDate).toBe('2026-03-31');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getLoadProfitability
// ─────────────────────────────────────────────────────────────────────────────

describe('getLoadProfitability()', () => {
  beforeEach(() => mockDb._reset());

  test('бросает ошибку если груз не найден', async () => {
    await expect(getLoadProfitability('nonexistent-id')).rejects.toThrow('Load not found');
  });

  test('возвращает полную структуру прибыльности груза', async () => {
    const load = await addLoad(makeLoad({ net_pay: 2500, miles: 500 }));
    await addExpense(makeExpense({ category: 'diesel', amount: 400, load_id: load.id }));
    await addExpense(makeExpense({ category: 'lumper', amount: 100, load_id: load.id }));

    const result = await getLoadProfitability(load.id);

    expect(result.loadId).toBe(load.id);
    expect(result.netPay).toBe(2500);
    expect(result.totalExpenses).toBe(500);
    expect(result.netProfit).toBe(2000);
    expect(result.expenses.diesel).toBe(400);
    expect(result.expenses.lumper).toBe(100);
  });

  test('profitPerMile = netProfit / miles', async () => {
    const load = await addLoad(makeLoad({ net_pay: 3000, miles: 600 }));

    const result = await getLoadProfitability(load.id);

    // netProfit = 3000 (нет расходов), profitPerMile = 3000/600 = 5.0
    expect(result.profitPerMile).toBeCloseTo(5.0, 2);
  });

  test('учитывает только расходы привязанные к данному грузу', async () => {
    const load1 = await addLoad(makeLoad({ net_pay: 2000, miles: 400 }));
    const load2 = await addLoad(makeLoad({ net_pay: 1800, miles: 350 }));

    // Расходы для load1
    await addExpense(makeExpense({ amount: 300, load_id: load1.id }));
    // Расходы для load2 — не должны попасть в load1
    await addExpense(makeExpense({ amount: 500, load_id: load2.id }));

    const result = await getLoadProfitability(load1.id);

    expect(result.totalExpenses).toBe(300);
    expect(result.netProfit).toBe(1700);
  });

  test('груз без расходов: netProfit = netPay', async () => {
    const load = await addLoad(makeLoad({ net_pay: 1500, miles: 300 }));

    const result = await getLoadProfitability(load.id);

    expect(result.totalExpenses).toBe(0);
    expect(result.netProfit).toBe(1500);
    expect(result.expenses).toEqual({});
  });

  test('возвращает origin, destination, brokerName из груза', async () => {
    const load = await addLoad(makeLoad({
      origin: 'Phoenix, AZ',
      destination: 'Denver, CO',
      broker_name: 'CH Robinson',
      net_pay: 2200,
    }));

    const result = await getLoadProfitability(load.id);

    expect(result.origin).toBe('Phoenix, AZ');
    expect(result.destination).toBe('Denver, CO');
    expect(result.brokerName).toBe('CH Robinson');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// learnVendorCategory & getVendorCategory
// ─────────────────────────────────────────────────────────────────────────────

describe('learnVendorCategory() / getVendorCategory()', () => {
  beforeEach(() => mockDb._reset());

  test('getVendorCategory возвращает null если вендор неизвестен', async () => {
    const result = await getVendorCategory('Unknown Vendor');
    expect(result).toBeNull();
  });

  test('learnVendorCategory сохраняет маппинг', async () => {
    await learnVendorCategory('Pilot Flying J', 'diesel');
    const category = await getVendorCategory('Pilot Flying J');
    expect(category).toBe('diesel');
  });

  test('поиск нечувствителен к регистру (trim + lowercase)', async () => {
    await learnVendorCategory('Love\'s Travel Stop', 'diesel');
    const category = await getVendorCategory('  Love\'s Travel Stop  ');
    expect(category).toBe('diesel');
  });

  test('перезапись: новая категория заменяет старую', async () => {
    await learnVendorCategory('Flying J', 'diesel');
    await learnVendorCategory('Flying J', 'maintenance'); // переучили

    const category = await getVendorCategory('Flying J');
    expect(category).toBe('maintenance');
  });

  test('не падает при пустом vendor или category', async () => {
    await expect(learnVendorCategory(null, 'diesel')).resolves.toBeUndefined();
    await expect(learnVendorCategory('Vendor', null)).resolves.toBeUndefined();
    await expect(learnVendorCategory('', '')).resolves.toBeUndefined();
  });

  test('getVendorCategory возвращает null при пустом vendor', async () => {
    const result = await getVendorCategory(null);
    expect(result).toBeNull();
  });

  test('несколько разных вендоров хранятся независимо', async () => {
    await learnVendorCategory('TA Travel Center', 'diesel');
    await learnVendorCategory('Motel 6', 'hotel');
    await learnVendorCategory('McDonald\'s', 'food');

    expect(await getVendorCategory('TA Travel Center')).toBe('diesel');
    expect(await getVendorCategory('Motel 6')).toBe('hotel');
    expect(await getVendorCategory('McDonald\'s')).toBe('food');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// clearAllExpenseData (reset)
// ─────────────────────────────────────────────────────────────────────────────

describe('clearAllExpenseData()', () => {
  test('вызывает execAsync с DELETE', async () => {
    mockDb._reset();
    await clearAllExpenseData();

    const execCalls = mockDb.execAsync.mock.calls;
    const hasDelete = execCalls.some(([sql]) => sql.includes('DELETE FROM expenses'));
    expect(hasDelete).toBeTruthy();
  });
});

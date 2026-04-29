/**
 * Tests for ifta/quarterlyCalculator.js
 *
 * Покрываем:
 * - getQuarterDates        — корректные start/end для каждого квартала
 * - filterTripsByQuarter   — фильтрация по quarter/year и по created_at
 * - aggregateStateMiles    — агрегация миль по штатам из массива поездок
 * - calculateIFTAReport    — математика налога (consumed − purchased) × rate
 * - generateIFTAPDF        — возвращает валидную HTML-строку
 * - IFTA_TAX_RATES         — ставки присутствуют и имеют разумные значения
 */

const {
  getQuarterDates,
  filterTripsByQuarter,
  aggregateStateMiles,
  calculateIFTAReport,
  generateIFTAPDF,
  IFTA_TAX_RATES,
} = require('../ifta/quarterlyCalculator');

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Строит поездку с полями quarter/year (бэкенд-формат). */
function makeTripByQuarter(quarter, year, extra = {}) {
  return { id: Math.random(), quarter, year, state_miles: { TX: 100 }, ...extra };
}

/** Строит поездку с полем created_at (клиентский парсинг даты). */
function makeTripByDate(isoDate, extra = {}) {
  return { id: Math.random(), created_at: isoDate, state_miles: { TX: 100 }, ...extra };
}

// ─────────────────────────────────────────────────────────────────────────────
// getQuarterDates
// ─────────────────────────────────────────────────────────────────────────────

describe('getQuarterDates()', () => {
  test('Q1 начинается 1 января и заканчивается 31 марта', () => {
    const { start, end } = getQuarterDates(1, 2026);

    expect(start.getFullYear()).toBe(2026);
    expect(start.getMonth()).toBe(0);   // январь (0-based)
    expect(start.getDate()).toBe(1);

    expect(end.getMonth()).toBe(2);     // март
    expect(end.getDate()).toBe(31);
  });

  test('Q2 начинается 1 апреля и заканчивается 30 июня', () => {
    const { start, end } = getQuarterDates(2, 2026);

    expect(start.getMonth()).toBe(3);   // апрель
    expect(start.getDate()).toBe(1);
    expect(end.getMonth()).toBe(5);     // июнь
    expect(end.getDate()).toBe(30);
  });

  test('Q3 начинается 1 июля и заканчивается 30 сентября', () => {
    const { start, end } = getQuarterDates(3, 2026);

    expect(start.getMonth()).toBe(6);   // июль
    expect(start.getDate()).toBe(1);
    expect(end.getMonth()).toBe(8);     // сентябрь
    expect(end.getDate()).toBe(30);
  });

  test('Q4 начинается 1 октября и заканчивается 31 декабря', () => {
    const { start, end } = getQuarterDates(4, 2026);

    expect(start.getMonth()).toBe(9);   // октябрь
    expect(start.getDate()).toBe(1);
    expect(end.getMonth()).toBe(11);    // декабрь
    expect(end.getDate()).toBe(31);
  });

  test('возвращает объекты типа Date', () => {
    const { start, end } = getQuarterDates(1, 2026);

    expect(start).toBeInstanceOf(Date);
    expect(end).toBeInstanceOf(Date);
  });

  test('start всегда раньше end', () => {
    for (let q = 1; q <= 4; q++) {
      const { start, end } = getQuarterDates(q, 2026);
      expect(start.getTime()).toBeLessThan(end.getTime());
    }
  });

  test('год передаётся корректно — Q1 2025 не равен Q1 2026', () => {
    const { start: s25 } = getQuarterDates(1, 2025);
    const { start: s26 } = getQuarterDates(1, 2026);

    expect(s25.getFullYear()).toBe(2025);
    expect(s26.getFullYear()).toBe(2026);
  });

  test('конец Q4 имеет время 23:59:59', () => {
    const { end } = getQuarterDates(4, 2026);

    expect(end.getHours()).toBe(23);
    expect(end.getMinutes()).toBe(59);
    expect(end.getSeconds()).toBe(59);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// filterTripsByQuarter
// ─────────────────────────────────────────────────────────────────────────────

describe('filterTripsByQuarter()', () => {
  test('возвращает пустой массив если входной массив пустой', () => {
    const result = filterTripsByQuarter([], 1, 2026);

    expect(result).toEqual([]);
  });

  test('фильтрует по полям quarter/year (бэкенд-формат)', () => {
    const trips = [
      makeTripByQuarter(1, 2026),
      makeTripByQuarter(2, 2026),
      makeTripByQuarter(1, 2025),
    ];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(1);
    expect(result[0].quarter).toBe(1);
    expect(result[0].year).toBe(2026);
  });

  test('фильтрует по created_at если quarter/year отсутствуют', () => {
    const trips = [
      makeTripByDate('2026-01-15'),   // Q1 2026
      makeTripByDate('2026-04-10'),   // Q2 2026
      makeTripByDate('2025-02-20'),   // Q1 2025
    ];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(1);
    expect(result[0].created_at).toBe('2026-01-15');
  });

  test('created_at: дата середины Q1 (15 января) включается', () => {
    const trips = [makeTripByDate('2026-01-15')];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(1);
  });

  test('created_at: дата середины Q1 (15 марта) включается', () => {
    const trips = [makeTripByDate('2026-03-15')];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(1);
  });

  test('created_at: дата середины Q2 (15 мая) не попадает в Q1', () => {
    const trips = [makeTripByDate('2026-05-15')];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(0);
  });

  test('поездка без quarter и без created_at исключается', () => {
    const trips = [{ id: 1, state_miles: { TX: 100 } }];

    const result = filterTripsByQuarter(trips, 1, 2026);

    expect(result).toHaveLength(0);
  });

  test('приоритет quarter/year над created_at: если оба есть — используются quarter/year', () => {
    // quarter=2, year=2026 но created_at указывает на Q1 2026
    const trip = {
      ...makeTripByDate('2026-01-15'),
      quarter: 2,
      year: 2026,
    };

    const resultQ1 = filterTripsByQuarter([trip], 1, 2026);
    const resultQ2 = filterTripsByQuarter([trip], 2, 2026);

    expect(resultQ1).toHaveLength(0);
    expect(resultQ2).toHaveLength(1);
  });

  test('возвращает все совпадающие поездки, а не только первую', () => {
    const trips = [
      makeTripByQuarter(3, 2026),
      makeTripByQuarter(3, 2026),
      makeTripByQuarter(3, 2026),
    ];

    const result = filterTripsByQuarter(trips, 3, 2026);

    expect(result).toHaveLength(3);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// aggregateStateMiles
// ─────────────────────────────────────────────────────────────────────────────

describe('aggregateStateMiles()', () => {
  test('возвращает пустой объект для пустого массива поездок', () => {
    const result = aggregateStateMiles([]);

    expect(result).toEqual({});
  });

  test('суммирует мили по одному штату из нескольких поездок', () => {
    const trips = [
      { state_miles: { TX: 200 } },
      { state_miles: { TX: 150 } },
    ];

    const result = aggregateStateMiles(trips);

    expect(result.TX).toBe(350);
  });

  test('суммирует мили по нескольким штатам', () => {
    const trips = [
      { state_miles: { TX: 200, OK: 80 } },
      { state_miles: { TX: 100, IL: 120 } },
    ];

    const result = aggregateStateMiles(trips);

    expect(result.TX).toBe(300);
    expect(result.OK).toBe(80);
    expect(result.IL).toBe(120);
  });

  test('поездка без state_miles не вызывает ошибку', () => {
    const trips = [
      { id: 1 },
      { state_miles: { TX: 50 } },
    ];

    const result = aggregateStateMiles(trips);

    expect(result.TX).toBe(50);
  });

  test('значения миль парсятся как числа (поддерживает строковые значения)', () => {
    const trips = [{ state_miles: { TX: '300.5' } }];

    const result = aggregateStateMiles(trips);

    expect(typeof result.TX).toBe('number');
    expect(result.TX).toBeCloseTo(300.5);
  });

  test('нулевые мили суммируются корректно', () => {
    const trips = [
      { state_miles: { TX: 0 } },
      { state_miles: { TX: 100 } },
    ];

    const result = aggregateStateMiles(trips);

    expect(result.TX).toBe(100);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// calculateIFTAReport
// ─────────────────────────────────────────────────────────────────────────────

describe('calculateIFTAReport()', () => {
  test('возвращает пустой массив для пустого stateMiles', () => {
    const result = calculateIFTAReport({});

    expect(result).toEqual([]);
  });

  test('базовый расчёт: consumed_gallons = total_miles / mpg', () => {
    const result = calculateIFTAReport({ TX: 650 }, 6.5);

    expect(result[0].state).toBe('TX');
    expect(result[0].consumed_gallons).toBeCloseTo(100, 2);
  });

  test('налог = net_gallons × tax_rate', () => {
    // TX rate = 0.20, 100 miles / 10 mpg = 10 consumed, 0 purchased → tax = 10 * 0.20 = 2.0
    const result = calculateIFTAReport({ TX: 100 }, 10, {});

    expect(result[0].net_gallons).toBeCloseTo(10, 2);
    expect(result[0].tax_due).toBeCloseTo(2.0, 3);
  });

  test('налог уменьшается на купленные галлоны: net_gallons = consumed − purchased', () => {
    // 100 miles / 10 mpg = 10 consumed; 8 purchased → net = 2; tax = 2 * 0.20 = 0.40
    const result = calculateIFTAReport({ TX: 100 }, 10, { TX: 8 });

    expect(result[0].consumed_gallons).toBeCloseTo(10, 2);
    expect(result[0].purchased_gallons).toBeCloseTo(8, 2);
    expect(result[0].net_gallons).toBeCloseTo(2, 2);
    expect(result[0].tax_due).toBeCloseTo(0.40, 3);
  });

  test('refund = true когда куплено больше чем потреблено', () => {
    // 100 miles / 10 mpg = 10 consumed; 20 purchased → net = -10 → refund
    const result = calculateIFTAReport({ TX: 100 }, 10, { TX: 20 });

    expect(result[0].net_gallons).toBeCloseTo(-10, 2);
    expect(result[0].tax_due).toBeLessThan(0);
    expect(result[0].refund).toBe(true);
  });

  test('refund = false когда налог к уплате', () => {
    const result = calculateIFTAReport({ TX: 100 }, 10, {});

    expect(result[0].refund).toBe(false);
  });

  test('дефолтный mpg = 6.5 используется если не передан', () => {
    const result = calculateIFTAReport({ TX: 650 });

    expect(result[0].consumed_gallons).toBeCloseTo(100, 2);
  });

  test('штат без ставки в IFTA_TAX_RATES даёт tax_due = 0', () => {
    const result = calculateIFTAReport({ ZZ: 100 }, 10);

    expect(result[0].tax_rate).toBe(0);
    expect(result[0].tax_due).toBe(0);
  });

  test('результат отсортирован по аббревиатуре штата', () => {
    const result = calculateIFTAReport({ TX: 100, AZ: 200, IL: 150 }, 10);

    const states = result.map(r => r.state);
    expect(states).toEqual([...states].sort());
  });

  test('несколько штатов обрабатываются независимо', () => {
    const result = calculateIFTAReport({ TX: 100, CA: 200 }, 10);

    expect(result).toHaveLength(2);
    const tx = result.find(r => r.state === 'TX');
    const ca = result.find(r => r.state === 'CA');
    expect(tx).toBeDefined();
    expect(ca).toBeDefined();
    // CA rate (0.824) > TX rate (0.20) → налог за CA больше при тех же галлонах
    expect(ca.tax_due).toBeGreaterThan(tx.tax_due);
  });

  test('total_miles округляется до 2 знаков', () => {
    const result = calculateIFTAReport({ TX: 123.456789 }, 10);

    expect(result[0].total_miles).toBe(123.46);
  });

  test('consumed_gallons округляется до 3 знаков', () => {
    const result = calculateIFTAReport({ TX: 100 }, 7);

    // 100 / 7 = 14.285714... → 14.286
    expect(result[0].consumed_gallons).toBe(14.286);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// generateIFTAPDF
// ─────────────────────────────────────────────────────────────────────────────

describe('generateIFTAPDF()', () => {
  const baseReportData = {
    quarter: 1,
    year: 2026,
    total_miles: 4500,
    avg_mpg: 6.5,
    total_trips: 12,
    total_tax_due: 187.50,
    states: [
      {
        state: 'TX',
        total_miles: 2000,
        consumed_gallons: 307.692,
        purchased_gallons: 280,
        net_gallons: 27.692,
        tax_rate: 0.20,
        tax_due: 5.54,
        refund: false,
      },
      {
        state: 'IL',
        total_miles: 1500,
        consumed_gallons: 230.769,
        purchased_gallons: 100,
        net_gallons: 130.769,
        tax_rate: 0.455,
        tax_due: 59.50,
        refund: false,
      },
    ],
  };

  test('возвращает строку', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(typeof result).toBe('string');
  });

  test('начинается с DOCTYPE html', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result.trim()).toMatch(/^<!DOCTYPE html>/i);
  });

  test('содержит номер квартала в заголовке', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('Q1');
  });

  test('содержит год отчёта', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('2026');
  });

  test('содержит строку для каждого штата из states', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('Texas');
    expect(result).toContain('Illinois');
  });

  test('содержит полное название штата вместо аббревиатуры', () => {
    const result = generateIFTAPDF(baseReportData);

    // TX → Texas должен быть раскрыт
    expect(result).toContain('Texas');
  });

  test('отображает TAX DUE при положительном total_tax_due', () => {
    const result = generateIFTAPDF({ ...baseReportData, total_tax_due: 50 });

    expect(result).toContain('TAX DUE');
    expect(result).not.toContain('CREDIT (REFUND)');
  });

  test('отображает CREDIT (REFUND) при отрицательном total_tax_due', () => {
    const result = generateIFTAPDF({ ...baseReportData, total_tax_due: -30 });

    expect(result).toContain('CREDIT (REFUND)');
    expect(result).not.toContain('TAX DUE');
  });

  test('имя водителя из driverInfo отображается в документе', () => {
    const result = generateIFTAPDF(baseReportData, {
      name: 'John Doe',
      company: 'Doe Trucking LLC',
      usdot: '12345678',
    });

    expect(result).toContain('John Doe');
    expect(result).toContain('Doe Trucking LLC');
    expect(result).toContain('12345678');
  });

  test('дефолтное имя водителя "Owner-Operator" если driverInfo не передан', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('Owner-Operator');
  });

  test('блок company не рендерится если company не передана', () => {
    const result = generateIFTAPDF(baseReportData, { name: 'Solo Driver' });

    // Лейбл Company не должен присутствовать
    expect(result).not.toContain('>Company<');
  });

  test('блок USDOT не рендерится если usdot не передан', () => {
    const result = generateIFTAPDF(baseReportData, { name: 'Solo Driver' });

    expect(result).not.toContain('USDOT #');
  });

  test('при пустом states отображается empty-notice вместо таблицы', () => {
    const result = generateIFTAPDF({ ...baseReportData, states: [] });

    expect(result).toContain('<div class="empty-notice">');
    expect(result).not.toContain('<table>');
  });

  test('при наличии states рендерится таблица', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('<table>');
    // Проверяем отсутствие блока empty-notice (класс есть в CSS, проверяем div)
    expect(result).not.toContain('<div class="empty-notice">');
  });

  test('total_miles отображается в итоговой строке таблицы', () => {
    const result = generateIFTAPDF(baseReportData);

    // toFixed(1) от 4500 = "4500.0"
    expect(result).toContain('4500.0');
  });

  test('генерируется корректный HTML для разных кварталов', () => {
    for (let q = 1; q <= 4; q++) {
      const result = generateIFTAPDF({ ...baseReportData, quarter: q });
      expect(result).toContain(`Q${q}`);
    }
  });

  test('branding "HaulWallet" присутствует в footer', () => {
    const result = generateIFTAPDF(baseReportData);

    expect(result).toContain('HaulWallet');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// IFTA_TAX_RATES
// ─────────────────────────────────────────────────────────────────────────────

describe('IFTA_TAX_RATES', () => {
  test('содержит ставки для ключевых штатов', () => {
    expect(IFTA_TAX_RATES).toHaveProperty('TX');
    expect(IFTA_TAX_RATES).toHaveProperty('CA');
    expect(IFTA_TAX_RATES).toHaveProperty('NY');
    expect(IFTA_TAX_RATES).toHaveProperty('FL');
    expect(IFTA_TAX_RATES).toHaveProperty('IL');
  });

  test('все ставки — положительные числа', () => {
    Object.entries(IFTA_TAX_RATES).forEach(([state, rate]) => {
      expect(typeof rate).toBe('number');
      expect(rate).toBeGreaterThan(0);
    });
  });

  test('все ставки находятся в реалистичном диапазоне (0 – 1.5 $/gallon)', () => {
    Object.entries(IFTA_TAX_RATES).forEach(([state, rate]) => {
      expect(rate).toBeLessThan(1.5);
    });
  });

  test('содержит как минимум 40 штатов', () => {
    expect(Object.keys(IFTA_TAX_RATES).length).toBeGreaterThanOrEqual(40);
  });

  test('аббревиатуры штатов состоят из 2 заглавных букв', () => {
    Object.keys(IFTA_TAX_RATES).forEach((abbr) => {
      expect(abbr).toMatch(/^[A-Z]{2}$/);
    });
  });

  test('ставка TX = 0.20', () => {
    expect(IFTA_TAX_RATES.TX).toBe(0.20);
  });

  test('ставка CA = 0.824 (самый высокий налог)', () => {
    expect(IFTA_TAX_RATES.CA).toBe(0.824);
  });
});

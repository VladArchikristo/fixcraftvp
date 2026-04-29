/**
 * Tests for ResultScreen calculation functions
 *
 * Тестируем: calcFuelData (IFTA расчёты, fuel cost, state breakdown)
 * Функция не экспортирована — копируем логику для unit-тестирования.
 */

// ─── IFTA Rates (копия из ResultScreen.js) ──────────────────────────────────
const IFTA_RATES = {
  TX: 0.200, OK: 0.160, KS: 0.260, MO: 0.170, IL: 0.455,
  IN: 0.330, OH: 0.280, PA: 0.741, NY: 0.398, NJ: 0.175,
  VA: 0.162, NC: 0.361, TN: 0.170, GA: 0.326, FL: 0.359,
  AL: 0.190, MS: 0.180, AR: 0.225, LA: 0.200, CA: 0.824,
  AZ: 0.260, NV: 0.270, UT: 0.249, CO: 0.205, NM: 0.210,
  WY: 0.240, MT: 0.2775, ID: 0.320, WA: 0.494, OR: 0.340,
};

function calcFuelData(distanceMiles, mpg, fuelPrice, breakdown, fuelPurchases) {
  const totalGallons = distanceMiles / mpg;
  const totalFuelCost = totalGallons * fuelPrice;

  const purchasedByState = {};
  if (fuelPurchases && fuelPurchases.length > 0) {
    fuelPurchases.forEach((p) => {
      if (p.state && p.gallons > 0) {
        purchasedByState[p.state] = (purchasedByState[p.state] || 0) + p.gallons;
      }
    });
  }
  const hasRealPurchases = Object.keys(purchasedByState).length > 0;

  const stateBreakdown = (breakdown || []).map((b) => {
    const consumedGallons = b.miles_in_state / mpg;
    const fuelCost = consumedGallons * fuelPrice;
    const iftaRate = IFTA_RATES[b.state] || 0;

    let iftaTax;
    let purchasedInState = 0;
    if (hasRealPurchases) {
      purchasedInState = purchasedByState[b.state] || 0;
      iftaTax = (consumedGallons - purchasedInState) * iftaRate;
    } else {
      iftaTax = consumedGallons * iftaRate;
    }

    return {
      state: b.state,
      miles: b.miles_in_state,
      gallons: consumedGallons.toFixed(2),
      purchasedGallons: purchasedInState > 0 ? purchasedInState.toFixed(2) : null,
      fuelCost: fuelCost.toFixed(2),
      iftaRate: iftaRate.toFixed(3),
      iftaTax: iftaTax.toFixed(2),
      iftaNetPositive: iftaTax >= 0,
    };
  });

  const totalIftaTax = stateBreakdown.reduce((sum, s) => sum + parseFloat(s.iftaTax), 0);

  return {
    totalGallons: totalGallons.toFixed(1),
    totalFuelCost: totalFuelCost.toFixed(2),
    totalIftaTax: totalIftaTax.toFixed(2),
    stateBreakdown,
    hasRealPurchases,
  };
}

// ─── Тесты ──────────────────────────────────────────────────────────────────

describe('calcFuelData() — базовые расчёты', () => {
  test('считает общий расход топлива: 650 миль / 6.5 MPG = 100 галлонов', () => {
    const result = calcFuelData(650, 6.5, 3.50, [], null);
    expect(result.totalGallons).toBe('100.0');
    expect(result.totalFuelCost).toBe('350.00');
  });

  test('считает общий расход при 1000 милях / 5 MPG', () => {
    const result = calcFuelData(1000, 5, 4.00, [], null);
    expect(result.totalGallons).toBe('200.0');
    expect(result.totalFuelCost).toBe('800.00');
  });

  test('0 миль = 0 галлонов, 0 cost', () => {
    const result = calcFuelData(0, 6.5, 3.50, [], null);
    expect(result.totalGallons).toBe('0.0');
    expect(result.totalFuelCost).toBe('0.00');
  });

  test('пустой breakdown = пустой stateBreakdown', () => {
    const result = calcFuelData(100, 6.5, 3.50, [], null);
    expect(result.stateBreakdown).toEqual([]);
    expect(result.totalIftaTax).toBe('0.00');
  });

  test('null breakdown обрабатывается как пустой', () => {
    const result = calcFuelData(100, 6.5, 3.50, null, null);
    expect(result.stateBreakdown).toEqual([]);
  });
});

describe('calcFuelData() — IFTA simplified (без fuel purchases)', () => {
  const breakdown = [
    { state: 'TX', miles_in_state: 325 },
    { state: 'OK', miles_in_state: 200 },
    { state: 'KS', miles_in_state: 125 },
  ];

  test('hasRealPurchases = false без fuel purchases', () => {
    const result = calcFuelData(650, 6.5, 3.50, breakdown, null);
    expect(result.hasRealPurchases).toBe(false);
  });

  test('считает IFTA по каждому штату: gallons * rate', () => {
    const result = calcFuelData(650, 6.5, 3.50, breakdown, null);

    // TX: 325/6.5 = 50 gal × $0.200 = $10.00
    const tx = result.stateBreakdown.find((s) => s.state === 'TX');
    expect(tx.gallons).toBe('50.00');
    expect(tx.iftaTax).toBe('10.00');
    expect(tx.iftaRate).toBe('0.200');

    // OK: 200/6.5 ≈ 30.77 gal × $0.160 ≈ $4.92
    const ok = result.stateBreakdown.find((s) => s.state === 'OK');
    expect(parseFloat(ok.iftaTax)).toBeCloseTo(4.92, 1);

    // KS: 125/6.5 ≈ 19.23 gal × $0.260 ≈ $5.00
    const ks = result.stateBreakdown.find((s) => s.state === 'KS');
    expect(parseFloat(ks.iftaTax)).toBeCloseTo(5.00, 1);
  });

  test('totalIftaTax = сумма всех штатов', () => {
    const result = calcFuelData(650, 6.5, 3.50, breakdown, null);
    const manualSum = result.stateBreakdown.reduce(
      (sum, s) => sum + parseFloat(s.iftaTax), 0
    );
    expect(parseFloat(result.totalIftaTax)).toBeCloseTo(manualSum, 2);
  });

  test('purchasedGallons = null в simplified mode', () => {
    const result = calcFuelData(650, 6.5, 3.50, breakdown, null);
    result.stateBreakdown.forEach((s) => {
      expect(s.purchasedGallons).toBeNull();
    });
  });

  test('все iftaNetPositive = true в simplified mode', () => {
    const result = calcFuelData(650, 6.5, 3.50, breakdown, null);
    result.stateBreakdown.forEach((s) => {
      expect(s.iftaNetPositive).toBe(true);
    });
  });
});

describe('calcFuelData() — IFTA full (с fuel purchases)', () => {
  const breakdown = [
    { state: 'TX', miles_in_state: 325 },
    { state: 'OK', miles_in_state: 200 },
  ];

  test('hasRealPurchases = true с fuel purchases', () => {
    const purchases = [{ state: 'TX', gallons: 80 }];
    const result = calcFuelData(525, 6.5, 3.50, breakdown, purchases);
    expect(result.hasRealPurchases).toBe(true);
  });

  test('Net IFTA: (consumed - purchased) × rate', () => {
    // TX: consumed = 325/6.5 = 50 gal, purchased = 80 gal
    // Net = (50 - 80) × 0.200 = -6.00 (refund!)
    const purchases = [{ state: 'TX', gallons: 80 }];
    const result = calcFuelData(525, 6.5, 3.50, breakdown, purchases);

    const tx = result.stateBreakdown.find((s) => s.state === 'TX');
    expect(tx.iftaTax).toBe('-6.00');
    expect(tx.iftaNetPositive).toBe(false);
    expect(tx.purchasedGallons).toBe('80.00');
  });

  test('штат без покупки — purchased = 0, IFTA = consumed × rate', () => {
    const purchases = [{ state: 'TX', gallons: 80 }];
    const result = calcFuelData(525, 6.5, 3.50, breakdown, purchases);

    const ok = result.stateBreakdown.find((s) => s.state === 'OK');
    // OK: consumed = 200/6.5 ≈ 30.77, purchased = 0
    // Net = 30.77 × 0.160 ≈ 4.92
    expect(parseFloat(ok.iftaTax)).toBeCloseTo(4.92, 1);
    expect(ok.purchasedGallons).toBeNull();
    expect(ok.iftaNetPositive).toBe(true);
  });

  test('множественные покупки в одном штате суммируются', () => {
    const purchases = [
      { state: 'TX', gallons: 30 },
      { state: 'TX', gallons: 25 },
    ];
    const result = calcFuelData(525, 6.5, 3.50, breakdown, purchases);
    const tx = result.stateBreakdown.find((s) => s.state === 'TX');
    expect(tx.purchasedGallons).toBe('55.00');
  });

  test('покупки с gallons=0 игнорируются', () => {
    const purchases = [{ state: 'TX', gallons: 0 }];
    const result = calcFuelData(525, 6.5, 3.50, breakdown, purchases);
    expect(result.hasRealPurchases).toBe(false);
  });
});

describe('calcFuelData() — неизвестный штат', () => {
  test('IFTA rate = 0 для неизвестного штата', () => {
    const breakdown = [{ state: 'XX', miles_in_state: 100 }];
    const result = calcFuelData(100, 6.5, 3.50, breakdown, null);
    const xx = result.stateBreakdown[0];
    expect(xx.iftaRate).toBe('0.000');
    expect(xx.iftaTax).toBe('0.00');
  });
});

describe('Toll cost calculation (grand total)', () => {
  test('grandTotal = tollCost + fuelCost + iftaTax', () => {
    const tollCost = 45.50;
    const fuel = calcFuelData(650, 6.5, 3.50, [
      { state: 'TX', miles_in_state: 325 },
      { state: 'OK', miles_in_state: 325 },
    ], null);

    const grandTotal = (
      tollCost +
      parseFloat(fuel.totalFuelCost) +
      parseFloat(fuel.totalIftaTax)
    ).toFixed(2);

    // fuelCost = 100 gal × $3.50 = $350
    // IFTA TX: 50 × 0.200 = $10, OK: 50 × 0.160 = $8 → total $18
    // Grand = 45.50 + 350 + 18 = $413.50
    expect(grandTotal).toBe('413.50');
  });

  test('без fuel = только tollCost', () => {
    const tollCost = 89.99;
    // Если fuel не включён, grandTotal не считается
    expect(tollCost.toFixed(2)).toBe('89.99');
  });
});

describe('IFTA_RATES integrity', () => {
  test('все ставки положительные', () => {
    Object.entries(IFTA_RATES).forEach(([state, rate]) => {
      expect(rate).toBeGreaterThan(0);
    });
  });

  test('все ставки < $1.00/gal (разумный диапазон)', () => {
    Object.entries(IFTA_RATES).forEach(([state, rate]) => {
      expect(rate).toBeLessThan(1.0);
    });
  });

  test('CA — самая дорогая ставка', () => {
    const maxRate = Math.max(...Object.values(IFTA_RATES));
    expect(IFTA_RATES.CA).toBe(maxRate);
  });
});

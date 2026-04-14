/**
 * Tests for stateDetectionService.js
 *
 * Тестируем чистую логику без внешних зависимостей.
 * Координаты проверены по реальным точкам в США.
 */

// Поскольку mobile использует ESM (import/export), подключаем через jest.unstable_mockModule
// Но файл написан на CommonJS-compatible ESM — используем babel transform через jest config.
// Здесь используем прямой require после настройки babel в jest.config.js (см. ниже).

const {
  detectState,
  detectStateCrossing,
  getStateName,
  getSupportedStates,
} = require('../services/stateDetectionService');

// ─────────────────────────────────────────────────────────────────────────────
// detectState — определение штата по координатам
// ─────────────────────────────────────────────────────────────────────────────

describe('detectState', () => {
  describe('центральные точки штатов (должны однозначно определяться)', () => {
    test('Даллас, Техас → TX', () => {
      const result = detectState(32.7767, -96.7970);
      expect(result).not.toBeNull();
      expect(result.state).toBe('TX');
    });

    test('Лос-Анджелес, Калифорния → CA', () => {
      const result = detectState(34.0522, -118.2437);
      expect(result).not.toBeNull();
      expect(result.state).toBe('CA');
    });

    test('Чикаго, Иллинойс → IL', () => {
      const result = detectState(41.8781, -87.6298);
      expect(result).not.toBeNull();
      expect(result.state).toBe('IL');
    });

    test('Атланта, Джорджия → GA', () => {
      const result = detectState(33.7490, -84.3880);
      expect(result).not.toBeNull();
      expect(result.state).toBe('GA');
    });

    test('Денвер, Колорадо → CO', () => {
      const result = detectState(39.7392, -104.9903);
      expect(result).not.toBeNull();
      expect(result.state).toBe('CO');
    });

    test('Майами, Флорида → FL', () => {
      const result = detectState(25.7617, -80.1918);
      expect(result).not.toBeNull();
      expect(result.state).toBe('FL');
    });

    test('Нью-Йорк, NY → NY', () => {
      const result = detectState(40.7128, -74.0060);
      expect(result).not.toBeNull();
      expect(result.state).toBe('NY');
    });

    test('Лас-Вегас, Невада → NV', () => {
      const result = detectState(36.1699, -115.1398);
      expect(result).not.toBeNull();
      expect(result.state).toBe('NV');
    });

    test('Портленд, Орегон → OR', () => {
      const result = detectState(45.5051, -122.6750);
      expect(result).not.toBeNull();
      expect(result.state).toBe('OR');
    });

    test('Феникс, Аризона → AZ', () => {
      const result = detectState(33.4484, -112.0740);
      expect(result).not.toBeNull();
      expect(result.state).toBe('AZ');
    });
  });

  describe('точки за пределами США (должны возвращать null)', () => {
    test('Торонто, Канада → null', () => {
      const result = detectState(43.6532, -79.3832);
      expect(result).toBeNull();
    });

    test('Мехико, Мексика → null', () => {
      const result = detectState(19.4326, -99.1332);
      expect(result).toBeNull();
    });

    test('Тихий океан → null', () => {
      const result = detectState(30.0, -150.0);
      expect(result).toBeNull();
    });

    test('Атлантический океан → null', () => {
      const result = detectState(35.0, -60.0);
      expect(result).toBeNull();
    });
  });

  describe('невалидные входные данные', () => {
    test('NaN координаты → null', () => {
      expect(detectState(NaN, -96.0)).toBeNull();
    });

    test('строки вместо чисел → null', () => {
      expect(detectState('не число', 'не число')).toBeNull();
    });

    test('undefined → null', () => {
      expect(detectState(undefined, undefined)).toBeNull();
    });
  });

  describe('структура ответа', () => {
    test('возвращает поле state (двухбуквенный код)', () => {
      const result = detectState(32.7767, -96.7970);
      expect(result).toHaveProperty('state');
      expect(result.state).toHaveLength(2);
    });

    test('возвращает поле stateName (полное название)', () => {
      const result = detectState(32.7767, -96.7970);
      expect(result).toHaveProperty('stateName');
      expect(typeof result.stateName).toBe('string');
      expect(result.stateName.length).toBeGreaterThan(0);
    });

    test('stateName для Техаса — "Texas"', () => {
      const result = detectState(32.7767, -96.7970);
      expect(result.stateName).toBe('Texas');
    });
  });

  describe('разрешение пересечений боксов (предпочтение меньшему штату)', () => {
    // Delaware (маленький) перекрывается с Пенсильванией и Мэрилендом
    test('Центр Delaware → DE (а не PA или MD)', () => {
      const result = detectState(39.1582, -75.5244);
      expect(result).not.toBeNull();
      expect(result.state).toBe('DE');
    });

    // Rhode Island — самый маленький штат
    test('Центр Rhode Island → RI', () => {
      const result = detectState(41.5801, -71.4774);
      expect(result).not.toBeNull();
      expect(result.state).toBe('RI');
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// detectStateCrossing — обнаружение пересечения границы штата
// ─────────────────────────────────────────────────────────────────────────────

describe('detectStateCrossing', () => {
  test('TX → OK: обнаруживает пересечение границы', () => {
    const prev = { latitude: 34.0, longitude: -97.5 }; // Южная Оклахома / Северный Техас
    const curr = { latitude: 35.5, longitude: -97.5 }; // Центр Оклахомы
    const result = detectStateCrossing(prev, curr);
    expect(result.crossed).toBe(true);
    expect(result.from).toBe('TX');
    expect(result.to).toBe('OK');
  });

  test('в пределах одного штата — crossed = false', () => {
    const prev = { latitude: 32.0, longitude: -96.0 }; // Техас
    const curr  = { latitude: 33.0, longitude: -97.0 }; // Тоже Техас
    const result = detectStateCrossing(prev, curr);
    expect(result.crossed).toBe(false);
    expect(result.from).toBe('TX');
    expect(result.to).toBe('TX');
  });

  test('CA → NV: пересечение на шоссе I-15 (Лас-Вегас)', () => {
    const prev = { latitude: 35.5, longitude: -115.5 }; // Калифорния
    const curr  = { latitude: 36.0, longitude: -114.5 }; // Невада
    const result = detectStateCrossing(prev, curr);
    expect(result.crossed).toBe(true);
  });

  test('null prevPoint → crossed = false', () => {
    const result = detectStateCrossing(null, { latitude: 32.7, longitude: -96.8 });
    expect(result.crossed).toBe(false);
  });

  test('null currPoint → crossed = false', () => {
    const result = detectStateCrossing({ latitude: 32.7, longitude: -96.8 }, null);
    expect(result.crossed).toBe(false);
  });

  test('оба null → crossed = false, from = null, to = null', () => {
    const result = detectStateCrossing(null, null);
    expect(result).toEqual({ crossed: false, from: null, to: null });
  });

  test('точка за пределами США → crossed = false', () => {
    const inUS     = { latitude: 32.7, longitude: -96.8 };
    const outside  = { latitude: 43.6, longitude: -79.4 }; // Канада
    const result = detectStateCrossing(inUS, outside);
    expect(result.crossed).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getStateName — получение полного названия штата
// ─────────────────────────────────────────────────────────────────────────────

describe('getStateName', () => {
  test('TX → "Texas"', () => {
    expect(getStateName('TX')).toBe('Texas');
  });

  test('CA → "California"', () => {
    expect(getStateName('CA')).toBe('California');
  });

  test('неизвестный код → возвращает сам код', () => {
    expect(getStateName('XX')).toBe('XX');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getSupportedStates — список всех штатов
// ─────────────────────────────────────────────────────────────────────────────

describe('getSupportedStates', () => {
  test('возвращает массив', () => {
    expect(Array.isArray(getSupportedStates())).toBe(true);
  });

  test('содержит 50 штатов (48 + AK + HI)', () => {
    expect(getSupportedStates()).toHaveLength(50);
  });

  test('содержит TX, CA, NY', () => {
    const states = getSupportedStates();
    expect(states).toContain('TX');
    expect(states).toContain('CA');
    expect(states).toContain('NY');
  });

  test('все коды двухбуквенные', () => {
    getSupportedStates().forEach(code => {
      expect(code).toHaveLength(2);
    });
  });
});

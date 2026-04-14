/**
 * Tests for backend/src/models/LoadTracking.js
 *
 * In-memory модель. Внешних зависимостей нет — моки не нужны.
 * Каждый тест сбрасывает состояние через изоляцию (jest.resetModules).
 */

// ─── Сброс in-memory store между тестами ─────────────────────────────────────
// LoadTracking хранит sessions в Map внутри модуля. Пересоздаём модуль
// перед каждым describe-блоком через jest.isolateModules.

let LoadTracking;

beforeEach(() => {
  jest.resetModules();
  LoadTracking = require('../src/models/LoadTracking');
});

// ─────────────────────────────────────────────────────────────────────────────
// create()
// ─────────────────────────────────────────────────────────────────────────────

describe('LoadTracking.create()', () => {
  test('возвращает объект сессии с нужными полями', () => {
    const session = LoadTracking.create(42, 'Chicago, IL');

    expect(session).toHaveProperty('token');
    expect(session).toHaveProperty('driverId', 42);
    expect(session).toHaveProperty('destination', 'Chicago, IL');
    expect(session).toHaveProperty('active', true);
    expect(session).toHaveProperty('lat', null);
    expect(session).toHaveProperty('lng', null);
    expect(session).toHaveProperty('speed', null);
    expect(session).toHaveProperty('eta', null);
    expect(session).toHaveProperty('createdAt');
    expect(session).toHaveProperty('updatedAt', null);
  });

  test('генерирует уникальный токен', () => {
    const s1 = LoadTracking.create(1, 'City A');
    const s2 = LoadTracking.create(1, 'City B');
    expect(s1.token).not.toBe(s2.token);
  });

  test('токен — 12 символов верхнего регистра без дефисов', () => {
    const { token } = LoadTracking.create(1, 'Dallas, TX');
    expect(token).toMatch(/^[A-Z0-9]{12}$/);
  });

  test('createdAt — валидная ISO-строка', () => {
    const { createdAt } = LoadTracking.create(1, 'Dallas, TX');
    expect(new Date(createdAt).toISOString()).toBe(createdAt);
  });

  test('сессия сразу доступна через get()', () => {
    const { token } = LoadTracking.create(5, 'Houston, TX');
    const fetched = LoadTracking.get(token);
    expect(fetched).not.toBeNull();
    expect(fetched.driverId).toBe(5);
  });

  test('пустой destination сохраняется как пустая строка', () => {
    const session = LoadTracking.create(1, '');
    expect(session.destination).toBe('');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// get()
// ─────────────────────────────────────────────────────────────────────────────

describe('LoadTracking.get()', () => {
  test('возвращает null для несуществующего токена', () => {
    const result = LoadTracking.get('NONEXISTENT123');
    expect(result).toBeNull();
  });

  test('возвращает сессию по правильному токену', () => {
    const created = LoadTracking.create(10, 'Miami, FL');
    const found = LoadTracking.get(created.token);
    expect(found.token).toBe(created.token);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// updatePosition()
// ─────────────────────────────────────────────────────────────────────────────

describe('LoadTracking.updatePosition()', () => {
  test('обновляет координаты и updatedAt', () => {
    const { token } = LoadTracking.create(1, 'Dallas, TX');
    const updated = LoadTracking.updatePosition(token, 32.77, -96.80, 55);

    expect(updated.lat).toBe(32.77);
    expect(updated.lng).toBe(-96.80);
    expect(updated.speed).toBe(55);
    expect(updated.updatedAt).not.toBeNull();
  });

  test('updatedAt — валидная ISO-строка', () => {
    const { token } = LoadTracking.create(1, 'Dallas, TX');
    const updated = LoadTracking.updatePosition(token, 32.77, -96.80, null);
    expect(new Date(updated.updatedAt).toISOString()).toBe(updated.updatedAt);
  });

  test('speed = null сохраняется', () => {
    const { token } = LoadTracking.create(1, 'Dallas, TX');
    const updated = LoadTracking.updatePosition(token, 32.77, -96.80, null);
    expect(updated.speed).toBeNull();
  });

  test('несуществующий токен → возвращает null', () => {
    const result = LoadTracking.updatePosition('BADTOKEN12345', 32.77, -96.80);
    expect(result).toBeNull();
  });

  test('остановленная сессия → возвращает null (нельзя обновить)', () => {
    const { token } = LoadTracking.create(1, 'Dallas, TX');
    LoadTracking.stop(token);
    const result = LoadTracking.updatePosition(token, 32.77, -96.80, 60);
    expect(result).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// stop()
// ─────────────────────────────────────────────────────────────────────────────

describe('LoadTracking.stop()', () => {
  test('деактивирует сессию (active = false)', () => {
    const { token } = LoadTracking.create(1, 'Atlanta, GA');
    LoadTracking.stop(token);
    const session = LoadTracking.get(token);
    expect(session.active).toBe(false);
  });

  test('обновляет updatedAt при остановке', () => {
    const { token } = LoadTracking.create(1, 'Atlanta, GA');
    const stopped = LoadTracking.stop(token);
    expect(stopped.updatedAt).not.toBeNull();
    expect(new Date(stopped.updatedAt).toISOString()).toBe(stopped.updatedAt);
  });

  test('несуществующий токен → null', () => {
    const result = LoadTracking.stop('NOTFOUND1234');
    expect(result).toBeNull();
  });

  test('сессия остаётся доступна через get() после остановки', () => {
    const { token } = LoadTracking.create(1, 'Atlanta, GA');
    LoadTracking.stop(token);
    const session = LoadTracking.get(token);
    expect(session).not.toBeNull();
    expect(session.active).toBe(false);
  });

  test('после остановки — updatePosition возвращает null (ссылка умирает)', () => {
    const { token } = LoadTracking.create(7, 'Phoenix, AZ');
    LoadTracking.stop(token);
    const result = LoadTracking.updatePosition(token, 33.44, -112.07, 0);
    expect(result).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Жизненный цикл полного сеанса (интеграционный)
// ─────────────────────────────────────────────────────────────────────────────

describe('полный жизненный цикл сессии', () => {
  test('создать → обновить позицию → остановить → ссылка inactive', () => {
    const session = LoadTracking.create(99, 'Los Angeles, CA');

    // Проверяем начальное состояние
    expect(session.active).toBe(true);
    expect(session.lat).toBeNull();

    // Отправляем позицию
    const updated = LoadTracking.updatePosition(session.token, 34.05, -118.24, 65);
    expect(updated.lat).toBe(34.05);
    expect(updated.active).toBe(true);

    // Доставка выполнена — стоп
    LoadTracking.stop(session.token);
    const final = LoadTracking.get(session.token);
    expect(final.active).toBe(false);

    // Брокерская ссылка должна показывать active = false
    expect(LoadTracking.get(session.token).active).toBe(false);
  });

  test('два водителя — раздельные независимые сессии', () => {
    const s1 = LoadTracking.create(1, 'Dallas, TX');
    const s2 = LoadTracking.create(2, 'Seattle, WA');

    LoadTracking.stop(s1.token);

    expect(LoadTracking.get(s1.token).active).toBe(false);
    expect(LoadTracking.get(s2.token).active).toBe(true);
  });
});

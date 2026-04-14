/**
 * Tests for loadTrackingService.js
 *
 * Мокируем: fetch, AsyncStorage, auth.getToken
 */

// ─── Моки ─────────────────────────────────────────────────────────────────────

// AsyncStorage mock
const mockStorage = {};
jest.mock('@react-native-async-storage/async-storage', () => ({
  setItem: jest.fn(async (key, val) => { mockStorage[key] = val; }),
  getItem: jest.fn(async (key) => mockStorage[key] ?? null),
  removeItem: jest.fn(async (key) => { delete mockStorage[key]; }),
}));

// auth.getToken mock
jest.mock('../services/auth', () => ({
  getToken: jest.fn().mockResolvedValue('mock-jwt-token'),
}));

// config mock
jest.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:3001',
}));

// fetch mock (глобальный)
global.fetch = jest.fn();

// ─── Импорт ────────────────────────────────────────────────────────────────────

const AsyncStorage = require('@react-native-async-storage/async-storage');
const loadTrackingService = require('../services/loadTrackingService').default;

// ─── Helper: создать mock ответ fetch ─────────────────────────────────────────

function mockFetchOk(body) {
  return {
    ok: true,
    json: jest.fn().mockResolvedValue(body),
  };
}

function mockFetchError(status, body = {}) {
  return {
    ok: false,
    status,
    json: jest.fn().mockResolvedValue(body),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// startTracking
// ─────────────────────────────────────────────────────────────────────────────

describe('loadTrackingService.startTracking()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(k => delete mockStorage[k]);
  });

  test('возвращает token, trackingUrl, destination при успехе', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({
      token: 'ABC123DEF456',
      trackingUrl: 'http://localhost:3000/track/ABC123DEF456',
      destination: 'Dallas, TX',
    }));

    const result = await loadTrackingService.startTracking('Dallas, TX');

    expect(result.token).toBe('ABC123DEF456');
    expect(result.trackingUrl).toBe('http://localhost:3000/track/ABC123DEF456');
    expect(result.destination).toBe('Dallas, TX');
  });

  test('вызывает POST /api/tracking/start с правильными параметрами', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({
      token: 'ABC123DEF456',
      trackingUrl: 'http://localhost:3000/track/ABC123DEF456',
      destination: 'Houston, TX',
    }));

    await loadTrackingService.startTracking('Houston, TX');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/tracking/start'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ destination: 'Houston, TX' }),
      })
    );
  });

  test('включает Authorization header с JWT токеном', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({
      token: 'TOKEN',
      trackingUrl: 'http://localhost:3000/track/TOKEN',
      destination: 'Miami, FL',
    }));

    await loadTrackingService.startTracking('Miami, FL');

    const [, options] = fetch.mock.calls[0];
    expect(options.headers['Authorization']).toBe('Bearer mock-jwt-token');
  });

  test('сохраняет сессию в AsyncStorage после успешного старта', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({
      token: 'STORED123456',
      trackingUrl: 'http://localhost:3000/track/STORED123456',
      destination: 'Chicago, IL',
    }));

    await loadTrackingService.startTracking('Chicago, IL');

    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      '@load_tracking_session',
      expect.any(String)
    );

    const stored = JSON.parse(mockStorage['@load_tracking_session']);
    expect(stored.token).toBe('STORED123456');
    expect(stored.destination).toBe('Chicago, IL');
  });

  test('бросает ошибку при ответе сервера не 2xx', async () => {
    fetch.mockResolvedValueOnce(mockFetchError(400, { error: 'destination is required' }));

    await expect(loadTrackingService.startTracking('')).rejects.toThrow('destination is required');
  });

  test('бросает ошибку при 500 с дефолтным сообщением', async () => {
    fetch.mockResolvedValueOnce(mockFetchError(500, {}));

    await expect(loadTrackingService.startTracking('test')).rejects.toThrow('Server error 500');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// sendLocationUpdate
// ─────────────────────────────────────────────────────────────────────────────

describe('loadTrackingService.sendLocationUpdate()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('отправляет POST /api/tracking/update с token, lat, lng, speed', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({ ok: true, updatedAt: new Date().toISOString() }));

    await loadTrackingService.sendLocationUpdate('TOKEN123', 32.77, -96.80, 65);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/tracking/update'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ token: 'TOKEN123', lat: 32.77, lng: -96.80, speed: 65 }),
      })
    );
  });

  test('не падает при пустом токене (ранний возврат)', async () => {
    await expect(
      loadTrackingService.sendLocationUpdate(null, 32.77, -96.80)
    ).resolves.toBeUndefined();

    expect(fetch).not.toHaveBeenCalled();
  });

  test('не пробрасывает ошибку при сетевой ошибке (graceful)', async () => {
    fetch.mockRejectedValueOnce(new Error('Network request failed'));

    await expect(
      loadTrackingService.sendLocationUpdate('TOKEN', 32.77, -96.80)
    ).resolves.toBeUndefined();
  });

  test('не пробрасывает ошибку при ответе 404', async () => {
    fetch.mockResolvedValueOnce(mockFetchError(404, { error: 'Session not found' }));

    await expect(
      loadTrackingService.sendLocationUpdate('DEAD_TOKEN', 32.77, -96.80)
    ).resolves.toBeUndefined();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// stopTracking
// ─────────────────────────────────────────────────────────────────────────────

describe('loadTrackingService.stopTracking()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(k => delete mockStorage[k]);
  });

  test('отправляет POST /api/tracking/stop с токеном', async () => {
    fetch.mockResolvedValueOnce(mockFetchOk({ ok: true, message: 'Tracking stopped. Load delivered.' }));

    await loadTrackingService.stopTracking('STOP_TOKEN');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/tracking/stop'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ token: 'STOP_TOKEN' }),
      })
    );
  });

  test('удаляет сессию из AsyncStorage после успешной остановки', async () => {
    mockStorage['@load_tracking_session'] = JSON.stringify({ token: 'T', destination: 'D' });
    fetch.mockResolvedValueOnce(mockFetchOk({ ok: true }));

    await loadTrackingService.stopTracking('T');

    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('@load_tracking_session');
    expect(mockStorage['@load_tracking_session']).toBeUndefined();
  });

  test('бросает ошибку при 403 (не твоя сессия)', async () => {
    fetch.mockResolvedValueOnce(mockFetchError(403, { error: 'Not your tracking session' }));

    await expect(loadTrackingService.stopTracking('OTHER_TOKEN')).rejects.toThrow(
      'Not your tracking session'
    );
  });

  test('ссылка умирает после Delivered — getActiveSession возвращает null', async () => {
    // Установить сессию
    mockStorage['@load_tracking_session'] = JSON.stringify({
      token: 'DELIVERED_TOKEN',
      trackingUrl: 'http://localhost:3000/track/DELIVERED_TOKEN',
      destination: 'Boston, MA',
    });

    fetch.mockResolvedValueOnce(mockFetchOk({ ok: true }));
    await loadTrackingService.stopTracking('DELIVERED_TOKEN');

    const session = await loadTrackingService.getActiveSession();
    expect(session).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// getActiveSession
// ─────────────────────────────────────────────────────────────────────────────

describe('loadTrackingService.getActiveSession()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(k => delete mockStorage[k]);
  });

  test('возвращает null если сессии нет', async () => {
    const result = await loadTrackingService.getActiveSession();
    expect(result).toBeNull();
  });

  test('восстанавливает сессию из AsyncStorage', async () => {
    const session = { token: 'PERSIST123', trackingUrl: 'http://x/track/P', destination: 'NY' };
    mockStorage['@load_tracking_session'] = JSON.stringify(session);

    const result = await loadTrackingService.getActiveSession();
    expect(result.token).toBe('PERSIST123');
    expect(result.destination).toBe('NY');
  });

  test('возвращает null при битом JSON в AsyncStorage', async () => {
    mockStorage['@load_tracking_session'] = 'NOT_VALID_JSON{{{';
    const result = await loadTrackingService.getActiveSession();
    expect(result).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// clearSession
// ─────────────────────────────────────────────────────────────────────────────

describe('loadTrackingService.clearSession()', () => {
  test('удаляет сессию из AsyncStorage без обращения к серверу', async () => {
    mockStorage['@load_tracking_session'] = JSON.stringify({ token: 'X' });

    await loadTrackingService.clearSession();

    expect(fetch).not.toHaveBeenCalled();
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('@load_tracking_session');
  });
});

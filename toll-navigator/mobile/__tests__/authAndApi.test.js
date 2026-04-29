/**
 * Тесты для auth.js, documentHistory.js и api.js
 *
 * Внешние зависимости замокированы:
 *   - expo-secure-store   (для auth.js)
 *   - @react-native-async-storage/async-storage (для documentHistory.js)
 *   - axios               (для api.js — перехватчик авторизации)
 *   - expo-constants      (для api.js — разрешение base URL)
 */

// ─── Моки внешних модулей ────────────────────────────────────────────────────

// expo-secure-store: простое in-memory хранилище
const secureStore = {};
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn((key, value) => {
    secureStore[key] = value;
    return Promise.resolve();
  }),
  getItemAsync: jest.fn((key) => Promise.resolve(secureStore[key] ?? null)),
  deleteItemAsync: jest.fn((key) => {
    delete secureStore[key];
    return Promise.resolve();
  }),
}));

// @react-native-async-storage/async-storage: простое in-memory хранилище
const asyncStorage = {};
jest.mock('@react-native-async-storage/async-storage', () => ({
  setItem: jest.fn((key, value) => {
    asyncStorage[key] = value;
    return Promise.resolve();
  }),
  getItem: jest.fn((key) => Promise.resolve(asyncStorage[key] ?? null)),
  removeItem: jest.fn((key) => {
    delete asyncStorage[key];
    return Promise.resolve();
  }),
}));

// expo-constants: возвращает пустой конфиг, чтобы api.js упал на config.js fallback
jest.mock('expo-constants', () => ({
  default: { expoConfig: null, manifest: null },
  expoConfig: null,
  manifest: null,
}));

// axios: возвращаем реальный axios, но перехватываем создание экземпляра
// чтобы проверить interceptors без сетевых вызовов
jest.mock('axios', () => {
  const actualAxios = jest.requireActual('axios');
  return actualAxios;
});

// ─── Импорты после регистрации моков ─────────────────────────────────────────

const SecureStore = require('expo-secure-store');
const AsyncStorage = require('@react-native-async-storage/async-storage');

const {
  saveToken,
  getToken,
  removeToken,
  saveUser,
  getUser,
  logout,
} = require('../services/auth');

const {
  getDocumentHistory,
  saveDocumentToHistory,
  deleteDocumentFromHistory,
  clearDocumentHistory,
  generateDocumentId,
  formatDocumentDate,
} = require('../services/documentHistory');

// ═════════════════════════════════════════════════════════════════════════════
// auth.js
// ═════════════════════════════════════════════════════════════════════════════

describe('auth — saveToken', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
  });

  test('вызывает SecureStore.setItemAsync с ключом toll_nav_jwt', async () => {
    await saveToken('abc123');
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith('toll_nav_jwt', 'abc123');
  });

  test('сохраняет произвольный токен без ошибок', async () => {
    await expect(saveToken('my-jwt-token')).resolves.toBeUndefined();
  });
});

describe('auth — getToken', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
  });

  test('возвращает null когда токена нет', async () => {
    const token = await getToken();
    expect(token).toBeNull();
  });

  test('возвращает сохранённый токен', async () => {
    await saveToken('stored-token');
    const token = await getToken();
    expect(token).toBe('stored-token');
  });

  test('вызывает SecureStore.getItemAsync с ключом toll_nav_jwt', async () => {
    await getToken();
    expect(SecureStore.getItemAsync).toHaveBeenCalledWith('toll_nav_jwt');
  });
});

describe('auth — removeToken', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
  });

  test('удаляет токен — после удаления getToken возвращает null', async () => {
    await saveToken('to-delete');
    await removeToken();
    const token = await getToken();
    expect(token).toBeNull();
  });

  test('вызывает SecureStore.deleteItemAsync с ключом toll_nav_jwt', async () => {
    await removeToken();
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('toll_nav_jwt');
  });
});

describe('auth — saveUser / getUser', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
  });

  test('getUser возвращает null когда пользователя нет', async () => {
    const user = await getUser();
    expect(user).toBeNull();
  });

  test('getUser возвращает сохранённого пользователя как объект', async () => {
    const user = { id: '42', email: 'test@example.com', name: 'Влад' };
    await saveUser(user);
    const retrieved = await getUser();
    expect(retrieved).toEqual(user);
  });

  test('saveUser сериализует объект в JSON', async () => {
    const user = { id: '1' };
    await saveUser(user);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'toll_nav_user',
      JSON.stringify(user)
    );
  });

  test('getUser десериализует JSON обратно в объект', async () => {
    const user = { id: '7', role: 'driver' };
    await saveUser(user);
    const retrieved = await getUser();
    expect(typeof retrieved).toBe('object');
    expect(retrieved.role).toBe('driver');
  });
});

describe('auth — logout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
  });

  test('удаляет и токен, и пользователя', async () => {
    await saveToken('jwt');
    await saveUser({ id: '1' });
    await logout();
    expect(await getToken()).toBeNull();
    expect(await getUser()).toBeNull();
  });

  test('вызывает deleteItemAsync дважды — для токена и пользователя', async () => {
    await logout();
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('toll_nav_jwt');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('toll_nav_user');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
  });

  test('не выбрасывает ошибку при пустом хранилище', async () => {
    await expect(logout()).resolves.toBeUndefined();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// documentHistory.js
// ═════════════════════════════════════════════════════════════════════════════

const HISTORY_KEY = '@toll_navigator:document_history';

describe('documentHistory — getDocumentHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(asyncStorage).forEach(k => delete asyncStorage[k]);
  });

  test('возвращает пустой массив когда хранилище пустое', async () => {
    const history = await getDocumentHistory();
    expect(history).toEqual([]);
  });

  test('возвращает список сохранённых документов', async () => {
    const docs = [{ id: 'doc_1', type: 'invoice' }];
    asyncStorage[HISTORY_KEY] = JSON.stringify(docs);
    const history = await getDocumentHistory();
    expect(history).toEqual(docs);
  });

  test('возвращает пустой массив при невалидном JSON', async () => {
    AsyncStorage.getItem.mockResolvedValueOnce('не-json');
    const history = await getDocumentHistory();
    expect(history).toEqual([]);
  });

  test('возвращает пустой массив если данные не массив', async () => {
    AsyncStorage.getItem.mockResolvedValueOnce(JSON.stringify({ id: 1 }));
    const history = await getDocumentHistory();
    expect(history).toEqual([]);
  });
});

describe('documentHistory — saveDocumentToHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(asyncStorage).forEach(k => delete asyncStorage[k]);
  });

  test('сохраняет первый документ и возвращает массив из одного элемента', async () => {
    const entry = { id: 'doc_1', type: 'bill_of_lading', date: '2026-01-01T00:00:00Z' };
    const result = await saveDocumentToHistory(entry);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual(entry);
  });

  test('новый документ добавляется в начало списка', async () => {
    const old = { id: 'doc_old', type: 'invoice' };
    const fresh = { id: 'doc_new', type: 'receipt' };
    await saveDocumentToHistory(old);
    const result = await saveDocumentToHistory(fresh);
    expect(result[0].id).toBe('doc_new');
    expect(result[1].id).toBe('doc_old');
  });

  test('не превышает лимит в 100 записей', async () => {
    // Заполняем хранилище 100 записями
    const existing = Array.from({ length: 100 }, (_, i) => ({ id: `doc_${i}` }));
    asyncStorage[HISTORY_KEY] = JSON.stringify(existing);
    const extra = { id: 'doc_extra' };
    const result = await saveDocumentToHistory(extra);
    expect(result).toHaveLength(100);
    expect(result[0].id).toBe('doc_extra');
  });

  test('вызывает AsyncStorage.setItem с корректным ключом', async () => {
    const entry = { id: 'doc_x' };
    await saveDocumentToHistory(entry);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      HISTORY_KEY,
      expect.any(String)
    );
  });
});

describe('documentHistory — deleteDocumentFromHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(asyncStorage).forEach(k => delete asyncStorage[k]);
  });

  test('удаляет документ по id', async () => {
    const docs = [
      { id: 'doc_1', type: 'a' },
      { id: 'doc_2', type: 'b' },
    ];
    asyncStorage[HISTORY_KEY] = JSON.stringify(docs);
    const result = await deleteDocumentFromHistory('doc_1');
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('doc_2');
  });

  test('возвращает тот же список если id не найден', async () => {
    const docs = [{ id: 'doc_1' }];
    asyncStorage[HISTORY_KEY] = JSON.stringify(docs);
    const result = await deleteDocumentFromHistory('nonexistent');
    expect(result).toHaveLength(1);
  });

  test('возвращает пустой массив после удаления единственного документа', async () => {
    asyncStorage[HISTORY_KEY] = JSON.stringify([{ id: 'only' }]);
    const result = await deleteDocumentFromHistory('only');
    expect(result).toEqual([]);
  });
});

describe('documentHistory — clearDocumentHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(asyncStorage).forEach(k => delete asyncStorage[k]);
  });

  test('вызывает AsyncStorage.removeItem с корректным ключом', async () => {
    await clearDocumentHistory();
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith(HISTORY_KEY);
  });

  test('после очистки getDocumentHistory возвращает пустой массив', async () => {
    asyncStorage[HISTORY_KEY] = JSON.stringify([{ id: 'doc_1' }]);
    await clearDocumentHistory();
    const history = await getDocumentHistory();
    expect(history).toEqual([]);
  });

  test('не выбрасывает ошибку при пустом хранилище', async () => {
    await expect(clearDocumentHistory()).resolves.toBeUndefined();
  });
});

describe('documentHistory — generateDocumentId', () => {
  test('возвращает строку', () => {
    expect(typeof generateDocumentId()).toBe('string');
  });

  test('начинается с "doc_"', () => {
    expect(generateDocumentId()).toMatch(/^doc_/);
  });

  test('каждый вызов возвращает уникальный id', () => {
    const ids = new Set(Array.from({ length: 20 }, () => generateDocumentId()));
    expect(ids.size).toBe(20);
  });

  test('содержит временную метку (числовую часть)', () => {
    const id = generateDocumentId();
    // Формат: doc_<timestamp>_<random>
    const parts = id.split('_');
    expect(parts.length).toBeGreaterThanOrEqual(3);
    expect(Number(parts[1])).toBeGreaterThan(0);
  });
});

describe('documentHistory — formatDocumentDate', () => {
  test('возвращает строку', () => {
    expect(typeof formatDocumentDate('2026-01-15T10:30:00Z')).toBe('string');
  });

  test('включает год из входной даты', () => {
    const result = formatDocumentDate('2026-01-15T10:30:00Z');
    expect(result).toContain('2026');
  });

  test('включает название месяца (короткое, en-US)', () => {
    const result = formatDocumentDate('2026-06-20T00:00:00Z');
    expect(result).toContain('Jun');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// api.js — разрешение base URL и auth interceptor
// ═════════════════════════════════════════════════════════════════════════════

describe('api — разрешение base URL', () => {
  const ORIGINAL_ENV = process.env;

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
    jest.resetModules();
  });

  test('EXPO_PUBLIC_API_URL инлайнится babel-preset-expo на этапе сборки — fallback config.js используется в тестах', () => {
    // babel-preset-expo заменяет process.env.EXPO_PUBLIC_* на литералы при трансформации,
    // поэтому runtime-изменение env не влияет на результат. Проверяем что baseURL всегда строка.
    let instance;
    jest.isolateModules(() => {
      instance = require('../services/api').default;
    });
    expect(typeof instance.defaults.baseURL).toBe('string');
    expect(instance.defaults.baseURL.length).toBeGreaterThan(0);
  });

  test('при отсутствии env использует fallback из config.js', () => {
    let instance;
    jest.isolateModules(() => {
      process.env = { ...ORIGINAL_ENV };
      delete process.env.EXPO_PUBLIC_API_URL;
      instance = require('../services/api').default;
    });
    // config.js fallback = 'https://api.haulwallet.com'
    expect(instance.defaults.baseURL).toBe('https://api.haulwallet.com');
  });

  test('timeout экземпляра равен 10000 мс', () => {
    const apiModule = require('../services/api');
    expect(apiModule.default.defaults.timeout).toBe(10000);
  });
});

describe('api — auth interceptor', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(secureStore).forEach(k => delete secureStore[k]);
    jest.resetModules();
  });

  test('добавляет заголовок Authorization: Bearer <token> когда токен есть', async () => {
    // Предварительно сохраняем токен в secureStore
    secureStore['toll_nav_jwt'] = 'valid-jwt-token';

    const apiModule = require('../services/api');
    const api = apiModule.default;

    // Вытаскиваем обработчик первого request-интерсептора
    const handler = api.interceptors.request.handlers[0];
    expect(handler).toBeDefined();

    const fakeConfig = { headers: {} };
    const result = await handler.fulfilled(fakeConfig);

    expect(result.headers.Authorization).toBe('Bearer valid-jwt-token');
  });

  test('не добавляет Authorization когда токена нет', async () => {
    // secureStore пуст
    const apiModule = require('../services/api');
    const api = apiModule.default;

    const handler = api.interceptors.request.handlers[0];
    const fakeConfig = { headers: {} };
    const result = await handler.fulfilled(fakeConfig);

    expect(result.headers.Authorization).toBeUndefined();
  });

  test('interceptor возвращает объект config', async () => {
    const apiModule = require('../services/api');
    const api = apiModule.default;

    const handler = api.interceptors.request.handlers[0];
    const fakeConfig = { headers: {}, url: '/test' };
    const result = await handler.fulfilled(fakeConfig);

    expect(result).toHaveProperty('url', '/test');
  });
});

'use strict';

/**
 * oauth.test.js — тесты OAuth flow и базовой аутентификации Toll Navigator.
 *
 * Стратегия изоляции:
 * - jest.mock('../src/db') — заменяет DatabaseSync-синглтон на in-memory стор,
 *   чтобы тесты не касались файловой системы и не требовали Node >= 22.5.
 * - jest.mock('../src/utils/oauthVerify') — изолирует внешние OAuth-провайдеры
 *   (Google, Apple). Каждый тест задаёт поведение мока сам.
 * - Создаём изолированное Express-приложение (не импортируем server.js,
 *   который сам стартует сервер и инициализирует БД при импорте).
 */

const request = require('supertest');
const express = require('express');
const jwt = require('jsonwebtoken');
const { createInMemoryDb } = require('./setup');

// ─── Моки (объявляем ДО любых require зависимых модулей) ─────────────────────

// Мок БД — будет переопределён в beforeEach через mockDb
jest.mock('../src/db', () => {
  const { createInMemoryDb } = require('./setup');
  return createInMemoryDb();
});

// Мок oauthVerify — методы переопределяются в каждом тесте
jest.mock('../src/utils/oauthVerify', () => ({
  verifyGoogleToken: jest.fn(),
  verifyAppleToken: jest.fn(),
}));

// middleware/auth мокаем минимально — /me не тестируется здесь
jest.mock('../src/middleware/auth', () => ({
  verifyToken: (req, res, next) => {
    req.userId = 1;
    next();
  },
}));

// ─── Импорты после моков ──────────────────────────────────────────────────────

const db = require('../src/db');
const { verifyGoogleToken, verifyAppleToken } = require('../src/utils/oauthVerify');
const authRouter = require('../src/routes/auth');

// ─── Вспомогательная фабрика приложения ──────────────────────────────────────

function buildApp() {
  const app = express();
  app.use(express.json());
  app.use('/api/auth', authRouter);
  return app;
}

// ─── Хелперы ─────────────────────────────────────────────────────────────────

const JWT_SECRET = 'changeme-in-production';

function decodeToken(token) {
  return jwt.verify(token, JWT_SECRET);
}

// ─── Setup / Teardown ─────────────────────────────────────────────────────────

beforeEach(() => {
  // Очищаем in-memory БД и сбрасываем моки перед каждым тестом
  db._reset();
  jest.clearAllMocks();
});

// ─── POST /api/auth/oauth ─────────────────────────────────────────────────────

describe('POST /api/auth/oauth', () => {

  // 1. Google OAuth — новый пользователь
  describe('Google OAuth — новый пользователь', () => {
    const googlePayload = {
      email: 'test@gmail.com',
      name: 'Test User',
      picture: 'https://example.com/photo.jpg',
      sub: 'google123',
    };

    beforeEach(() => {
      verifyGoogleToken.mockResolvedValue(googlePayload);
    });

    it('возвращает статус 200', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(res.status).toBe(200);
    });

    it('возвращает JWT-токен в поле token', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(res.body).toHaveProperty('token');
      expect(typeof res.body.token).toBe('string');
    });

    it('JWT-токен содержит корректный email пользователя', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      const decoded = decodeToken(res.body.token);
      expect(decoded.email).toBe('test@gmail.com');
    });

    it('возвращает объект user с email', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(res.body.user).toMatchObject({ email: 'test@gmail.com' });
    });

    it('возвращает user.name из Google-токена', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(res.body.user.name).toBe('Test User');
    });

    it('возвращает user.oauth_provider === "google"', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(res.body.user.oauth_provider).toBe('google');
    });

    it('вызывает verifyGoogleToken с переданным токеном', async () => {
      await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'fake_token' });

      expect(verifyGoogleToken).toHaveBeenCalledWith('fake_token');
    });
  });

  // 2. Google OAuth — существующий пользователь (не создаётся дубль)
  describe('Google OAuth — существующий пользователь', () => {
    const googlePayload = {
      email: 'existing@gmail.com',
      name: 'Existing User',
      picture: null,
      sub: 'google_existing_789',
    };

    beforeEach(() => {
      verifyGoogleToken.mockResolvedValue(googlePayload);
    });

    it('возвращает статус 200 при повторном входе', async () => {
      const app = buildApp();
      // Первый вход — создаём пользователя
      await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_first' });

      // Второй вход — тот же пользователь
      const res = await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_second' });

      expect(res.status).toBe(200);
    });

    it('не создаёт дубль пользователя при повторном входе', async () => {
      const app = buildApp();
      await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_first' });

      await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_second' });

      // В in-memory БД должен быть ровно один пользователь
      expect(db._users.size).toBe(1);
    });

    it('возвращает тот же id пользователя при повторном входе', async () => {
      const app = buildApp();
      const first = await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_first' });

      const second = await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'token_second' });

      expect(second.body.user.id).toBe(first.body.user.id);
    });

    it('находит существующего пользователя по oauth_id', async () => {
      const app = buildApp();
      await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'tok' });

      const res = await request(app)
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'tok' });

      expect(res.body.user.email).toBe('existing@gmail.com');
    });
  });

  // 3. Apple OAuth — новый пользователь
  describe('Apple OAuth — новый пользователь', () => {
    const applePayload = {
      email: 'test@icloud.com',
      sub: 'apple456',
    };

    beforeEach(() => {
      verifyAppleToken.mockResolvedValue(applePayload);
    });

    it('возвращает статус 200', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(res.status).toBe(200);
    });

    it('возвращает JWT-токен', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(res.body).toHaveProperty('token');
      expect(typeof res.body.token).toBe('string');
    });

    it('возвращает user.oauth_provider === "apple"', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(res.body.user.oauth_provider).toBe('apple');
    });

    it('возвращает user.email из Apple-токена', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(res.body.user.email).toBe('test@icloud.com');
    });

    it('использует name из тела запроса (Apple не передаёт имя в токене)', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(res.body.user.name).toBe('Apple User');
    });

    it('вызывает verifyAppleToken с переданным токеном', async () => {
      await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'fake_apple_token', name: 'Apple User' });

      expect(verifyAppleToken).toHaveBeenCalledWith('fake_apple_token');
    });

    it('принимает email из тела запроса если Apple не вернул его в токене', async () => {
      // Apple не присылает email при повторных входах
      verifyAppleToken.mockResolvedValue({ email: null, sub: 'apple_no_email_sub' });

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'tok', email: 'fallback@icloud.com', name: 'No Email User' });

      expect(res.status).toBe(200);
      expect(res.body.user.email).toBe('fallback@icloud.com');
    });
  });

  // 4. Неверный провайдер
  describe('Неверный провайдер', () => {
    it('возвращает 400 при provider = "facebook"', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'facebook', token: 'xxx' });

      expect(res.status).toBe(400);
    });

    it('возвращает 400 при provider = "twitter"', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'twitter', token: 'xxx' });

      expect(res.status).toBe(400);
    });

    it('возвращает сообщение об ошибке в поле error', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'facebook', token: 'xxx' });

      expect(res.body).toHaveProperty('error');
    });

    it('возвращает 400 если provider отсутствует в теле', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ token: 'xxx' });

      expect(res.status).toBe(400);
    });

    it('возвращает 400 если token отсутствует в теле', async () => {
      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google' });

      expect(res.status).toBe(400);
    });
  });

  // 5. Невалидный токен Google — verifyGoogleToken бросает ошибку
  describe('Невалидный токен Google', () => {
    it('возвращает 401 при ошибке "Invalid token"', async () => {
      verifyGoogleToken.mockRejectedValue(new Error('Invalid token signature'));

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'bad_token' });

      expect(res.status).toBe(401);
    });

    it('возвращает 401 при ошибке "Token used too late"', async () => {
      verifyGoogleToken.mockRejectedValue(new Error('Token used too late'));

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'expired_token' });

      expect(res.status).toBe(401);
    });

    it('возвращает 401 при ошибке "Wrong number of segments"', async () => {
      verifyGoogleToken.mockRejectedValue(new Error('Wrong number of segments'));

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'malformed' });

      expect(res.status).toBe(401);
    });

    it('возвращает 500 при непредвиденной серверной ошибке (не проблема токена)', async () => {
      verifyGoogleToken.mockRejectedValue(new Error('Network timeout'));

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'some_token' });

      expect(res.status).toBe(500);
    });

    it('возвращает поле error в теле ответа при невалидном токене', async () => {
      verifyGoogleToken.mockRejectedValue(new Error('Invalid token'));

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'google', token: 'bad_token' });

      expect(res.body).toHaveProperty('error');
    });
  });

  // Граничный случай: Apple без email и без fallback email в теле
  describe('Apple OAuth — нет email ни в токене ни в теле (новый пользователь)', () => {
    it('возвращает 400 если невозможно создать пользователя без email', async () => {
      verifyAppleToken.mockResolvedValue({ email: null, sub: 'apple_no_email_at_all' });

      const res = await request(buildApp())
        .post('/api/auth/oauth')
        .send({ provider: 'apple', token: 'tok' });
      // email нет ни в токене, ни в body — новый пользователь не может быть создан
      expect(res.status).toBe(400);
    });
  });
});

// ─── POST /api/auth/register ──────────────────────────────────────────────────

describe('POST /api/auth/register', () => {
  it('создаёт нового пользователя и возвращает 201', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'new@example.com', password: 'SecurePass123' });

    expect(res.status).toBe(201);
  });

  it('возвращает JWT-токен после регистрации', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'jwt@example.com', password: 'SecurePass123' });

    expect(res.body).toHaveProperty('token');
    expect(typeof res.body.token).toBe('string');
  });

  it('JWT содержит корректный email зарегистрированного пользователя', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'decode@example.com', password: 'pass' });

    const decoded = decodeToken(res.body.token);
    expect(decoded.email).toBe('decode@example.com');
  });

  it('возвращает объект user с email и truck_type по умолчанию', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'truck@example.com', password: 'pass' });

    expect(res.body.user).toMatchObject({
      email: 'truck@example.com',
      truck_type: '2-axle',
    });
  });

  it('принимает кастомный truck_type', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'custom@example.com', password: 'pass', truck_type: '5-axle' });

    expect(res.body.user.truck_type).toBe('5-axle');
  });

  it('возвращает 409 при попытке зарегистрировать существующий email', async () => {
    const app = buildApp();
    await request(app)
      .post('/api/auth/register')
      .send({ email: 'dup@example.com', password: 'pass1' });

    const res = await request(app)
      .post('/api/auth/register')
      .send({ email: 'dup@example.com', password: 'pass2' });

    expect(res.status).toBe(409);
  });

  it('возвращает 400 если email отсутствует', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ password: 'pass' });

    expect(res.status).toBe(400);
  });

  it('возвращает 400 если password отсутствует', async () => {
    const res = await request(buildApp())
      .post('/api/auth/register')
      .send({ email: 'nopass@example.com' });

    expect(res.status).toBe(400);
  });
});

// ─── POST /api/auth/login ─────────────────────────────────────────────────────

describe('POST /api/auth/login', () => {
  // Регистрируем пользователя один раз для тестов логина
  const TEST_EMAIL = 'login@example.com';
  const TEST_PASSWORD = 'CorrectPassword123';

  beforeEach(async () => {
    // Создаём пользователя напрямую через API (bcrypt работает с реальными хэшами)
    await request(buildApp())
      .post('/api/auth/register')
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });
  });

  it('возвращает 200 при корректных учётных данных', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });

    expect(res.status).toBe(200);
  });

  it('возвращает JWT-токен при успешном входе', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });

    expect(res.body).toHaveProperty('token');
    expect(typeof res.body.token).toBe('string');
  });

  it('JWT содержит корректный userId и email', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });

    const decoded = decodeToken(res.body.token);
    expect(decoded.email).toBe(TEST_EMAIL);
    expect(decoded).toHaveProperty('userId');
  });

  it('возвращает объект user без поля password', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: TEST_PASSWORD });

    expect(res.body.user).not.toHaveProperty('password');
  });

  it('возвращает 401 при неверном пароле', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: 'WrongPassword!' });

    expect(res.status).toBe(401);
  });

  it('возвращает 401 если пользователь не существует', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: 'ghost@example.com', password: 'any' });

    expect(res.status).toBe(401);
  });

  it('возвращает 400 если email отсутствует', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ password: TEST_PASSWORD });

    expect(res.status).toBe(400);
  });

  it('возвращает 400 если password отсутствует', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL });

    expect(res.status).toBe(400);
  });

  it('возвращает поле error в теле при неверных данных', async () => {
    const res = await request(buildApp())
      .post('/api/auth/login')
      .send({ email: TEST_EMAIL, password: 'wrong' });

    expect(res.body).toHaveProperty('error');
  });
});

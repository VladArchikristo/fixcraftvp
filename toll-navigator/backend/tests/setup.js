/**
 * setup.js — глобальный Jest setup для тестов Toll Navigator backend.
 *
 * Проблема: db.js использует встроенный Node.js `node:sqlite` (DatabaseSync),
 * который требует Node >= 22.5 и не поддерживается Jest-трансформером напрямую.
 * Решение: мокаем '../db' через jest.mock() прямо в тестах, а здесь
 * экспортируем фабрику in-memory SQLite базы через better-sqlite3.
 *
 * Если better-sqlite3 не установлен — фабрика создаёт лёгкий in-memory стор
 * на Map, совместимый с API из db.js (prepare/run/get/all/exec).
 */

'use strict';

/**
 * Создаёт минимальный in-memory стор, совместимый с интерфейсом DatabaseSync.
 * Поддерживает операции, используемые в auth.js:
 *   db.prepare(sql).get(...params)
 *   db.prepare(sql).run(...params)
 *   db.exec(sql)                   (no-op для тестов)
 */
function createInMemoryDb() {
  // Хранилище пользователей
  const users = new Map(); // id -> user object
  let nextId = 1;

  function parseQuery(sql) {
    const s = sql.trim().toUpperCase();
    if (s.startsWith('SELECT') && s.includes('FROM USERS') && s.includes('WHERE EMAIL')) {
      return 'SELECT_USER_BY_EMAIL';
    }
    if (s.startsWith('SELECT') && s.includes('FROM USERS') && s.includes('WHERE OAUTH_PROVIDER') && s.includes('OAUTH_ID')) {
      return 'SELECT_USER_BY_OAUTH';
    }
    if (s.startsWith('SELECT') && s.includes('FROM USERS') && s.includes('WHERE ID')) {
      return 'SELECT_USER_BY_ID';
    }
    if (s.startsWith('INSERT INTO USERS') && s.includes('EMAIL, PASSWORD')) {
      if (s.includes('OAUTH_PROVIDER')) return 'INSERT_USER_OAUTH';
      return 'INSERT_USER_PASSWORD';
    }
    if (s.startsWith('UPDATE USERS') && s.includes('SET OAUTH_PROVIDER')) {
      return 'UPDATE_USER_OAUTH';
    }
    if (s.startsWith('SELECT') && s.includes('FROM USERS') && !s.includes('WHERE')) {
      return 'SELECT_USER_FULL'; // для /me
    }
    return 'UNKNOWN';
  }

  function prepare(sql) {
    const type = parseQuery(sql);

    return {
      get(...params) {
        switch (type) {
          case 'SELECT_USER_BY_EMAIL': {
            const email = params[0];
            for (const u of users.values()) {
              if (u.email === email) return { ...u };
            }
            return undefined;
          }
          case 'SELECT_USER_BY_OAUTH': {
            const [provider, oauthId] = params;
            for (const u of users.values()) {
              if (u.oauth_provider === provider && u.oauth_id === oauthId) return { ...u };
            }
            return undefined;
          }
          case 'SELECT_USER_BY_ID': {
            const id = params[0];
            return users.has(id) ? { ...users.get(id) } : undefined;
          }
          case 'SELECT_USER_FULL': {
            // PRAGMA table_info — возвращаем пустой массив
            return undefined;
          }
          default:
            return undefined;
        }
      },

      all(...params) {
        // Используется в PRAGMA table_info(routes) — возвращаем пустой массив
        return [];
      },

      run(...params) {
        switch (type) {
          case 'INSERT_USER_PASSWORD': {
            const [email, hash, truck_type] = params;
            const id = nextId++;
            users.set(id, {
              id,
              email,
              password: hash,
              name: null,
              truck_type: truck_type || '2-axle',
              oauth_provider: null,
              oauth_id: null,
              avatar_url: null,
              created_at: new Date().toISOString(),
            });
            return { lastInsertRowid: id };
          }
          case 'INSERT_USER_OAUTH': {
            // SQL: INSERT INTO users (email, password, name, oauth_provider, oauth_id, avatar_url)
            //      VALUES (?, NULL, ?, ?, ?, ?)
            // Параметры (5 штук, password = NULL в SQL, не передаётся как param):
            //   params[0] = email
            //   params[1] = name
            //   params[2] = oauth_provider
            //   params[3] = oauth_id
            //   params[4] = avatar_url
            const [email, name, oauth_provider, oauth_id, avatar_url] = params;
            const id = nextId++;
            users.set(id, {
              id,
              email,
              password: null,
              name: name || null,
              truck_type: '2-axle',
              oauth_provider,
              oauth_id,
              avatar_url: avatar_url || null,
              created_at: new Date().toISOString(),
            });
            return { lastInsertRowid: id };
          }
          case 'UPDATE_USER_OAUTH': {
            // UPDATE users SET oauth_provider=?, oauth_id=?, avatar_url=... WHERE id=?
            const [provider, oauthId, avatarUrl, userId] = params;
            const u = users.get(userId);
            if (u) {
              u.oauth_provider = provider;
              u.oauth_id = oauthId;
              u.avatar_url = u.avatar_url || avatarUrl;
              users.set(userId, u);
            }
            return { changes: u ? 1 : 0 };
          }
          default:
            return { lastInsertRowid: 0, changes: 0 };
        }
      },
    };
  }

  return {
    prepare,
    exec() {}, // no-op
    _users: users, // для инспекции в тестах
    _reset() {
      users.clear();
      nextId = 1;
    },
  };
}

module.exports = { createInMemoryDb };

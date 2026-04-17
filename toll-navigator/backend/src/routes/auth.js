const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../db');
const { verifyGoogleToken, verifyAppleToken } = require('../utils/oauthVerify');

const router = express.Router();
const JWT_SECRET = process.env.JWT_SECRET || 'changeme-in-production';

// POST /api/auth/register
router.post('/register', async (req, res) => {
  try {
    const { email, password, truck_type = '2-axle' } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    // Проверяем существует ли пользователь
    const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
    if (existing) {
      return res.status(409).json({ error: 'Email already registered' });
    }

    const hash = await bcrypt.hash(password, 10);
    const stmt = db.prepare(
      'INSERT INTO users (email, password, truck_type) VALUES (?, ?, ?)'
    );
    const result = stmt.run(email, hash, truck_type);

    const token = jwt.sign(
      { userId: result.lastInsertRowid, email },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.status(201).json({
      token,
      user: { id: result.lastInsertRowid, email, truck_type }
    });
  } catch (err) {
    console.error('Register error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const valid = await bcrypt.compare(password, user.password);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign(
      { userId: user.id, email: user.email },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.json({
      token,
      user: { id: user.id, email: user.email, truck_type: user.truck_type }
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/auth/oauth
// Body: { provider: 'google'|'apple', token: '<id_token>', name?: string, email?: string }
// Apple doesn't always send email in JWT — client should pass it in body on first login.
router.post('/oauth', async (req, res) => {
  try {
    const { provider, token, name: bodyName, email: bodyEmail } = req.body;

    if (!provider || !token) {
      return res.status(400).json({ error: 'provider and token are required' });
    }
    if (provider !== 'google' && provider !== 'apple') {
      return res.status(400).json({ error: 'provider must be google or apple' });
    }

    let oauthId, email, name, avatar_url;

    if (provider === 'google') {
      const payload = await verifyGoogleToken(token);
      oauthId = payload.sub;
      email = payload.email;
      name = payload.name || bodyName || null;
      avatar_url = payload.picture || null;
    } else {
      // Apple: email only present on first authorization; subsequent calls omit it
      const payload = await verifyAppleToken(token);
      oauthId = payload.sub;
      email = payload.email || bodyEmail || null;
      name = bodyName || null;
      avatar_url = null;
    }

    if (!email && !oauthId) {
      return res.status(400).json({ error: 'Could not determine user identity from token' });
    }

    // Try to find existing user by oauth_provider+oauth_id first (most reliable),
    // then fall back to email lookup (handles case where user registered with password before)
    let user = db.prepare(
      'SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?'
    ).get(provider, oauthId);

    if (!user && email) {
      user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
    }

    if (user) {
      // Existing user — update OAuth fields if they were missing (e.g. password-registered user)
      if (!user.oauth_id) {
        db.prepare(
          'UPDATE users SET oauth_provider = ?, oauth_id = ?, avatar_url = COALESCE(avatar_url, ?) WHERE id = ?'
        ).run(provider, oauthId, avatar_url, user.id);
      }
    } else {
      // New user — register with null password
      if (!email) {
        return res.status(400).json({ error: 'Email is required for new OAuth users' });
      }
      const result = db.prepare(
        'INSERT INTO users (email, password, name, oauth_provider, oauth_id, avatar_url) VALUES (?, NULL, ?, ?, ?, ?)'
      ).run(email, name, provider, oauthId, avatar_url);
      user = db.prepare('SELECT * FROM users WHERE id = ?').get(result.lastInsertRowid);
    }

    const jwtToken = jwt.sign(
      { userId: user.id, email: user.email },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.json({
      token: jwtToken,
      user: {
        id: user.id,
        email: user.email,
        name: user.name || null,
        truck_type: user.truck_type,
        oauth_provider: user.oauth_provider || null,
      },
    });
  } catch (err) {
    console.error('OAuth error:', err);
    // Distinguish token verification failures from server errors
    if (err.message && (err.message.includes('Invalid token') || err.message.includes('Token used too late') || err.message.includes('Wrong number of segments'))) {
      return res.status(401).json({ error: 'Invalid or expired OAuth token' });
    }
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/auth/me — профиль текущего пользователя
router.get('/me', require('../middleware/auth').verifyToken, (req, res) => {
  const user = db.prepare('SELECT id, email, name, truck_type, oauth_provider, created_at FROM users WHERE id = ?').get(req.userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json(user);
});

module.exports = router;

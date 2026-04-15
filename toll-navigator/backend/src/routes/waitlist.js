const express = require('express');
const rateLimit = require('express-rate-limit');
const router = express.Router();
const db = require('../db');

// Rate-limit: 5 запросов в минуту на waitlist endpoints
const waitlistLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 5,
  message: { error: 'Too many requests, try again in a minute.' }
});
router.use(waitlistLimiter);

// POST /api/waitlist - Add email to waitlist
router.post('/', (req, res) => {
  const { email } = req.body;

  if (!email || typeof email !== 'string') {
    return res.status(400).json({ error: 'email_required' });
  }

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.trim())) {
    return res.status(400).json({ error: 'invalid_email' });
  }

  const cleanEmail = email.trim().toLowerCase();

  try {
    const existing = db.prepare('SELECT id FROM waitlist WHERE email = ?').get(cleanEmail);
    if (existing) {
      return res.status(200).json({ success: true, message: 'Already registered' });
    }

    const source = req.body.source || 'landing';
    db.prepare('INSERT INTO waitlist (email, source) VALUES (?, ?)').run(cleanEmail, source);

    const count = db.prepare('SELECT COUNT(*) as total FROM waitlist').get();

    res.status(201).json({
      success: true,
      message: 'Added to waitlist',
      position: count.total
    });
  } catch (err) {
    console.error('Waitlist error:', err.message);
    res.status(500).json({ error: 'server_error' });
  }
});

// GET /api/waitlist - List all entries (protected by API key)
router.get('/', (req, res) => {
  const apiKey = req.headers['x-api-key'];
  const expectedKey = process.env.WAITLIST_API_KEY;

  if (!expectedKey || apiKey !== expectedKey) {
    return res.status(401).json({ error: 'unauthorized' });
  }

  try {
    const entries = db.prepare(
      'SELECT id, email, source, created_at FROM waitlist ORDER BY created_at DESC'
    ).all();

    res.json({ total: entries.length, entries });
  } catch (err) {
    console.error('Waitlist list error:', err.message);
    res.status(500).json({ error: 'server_error' });
  }
});

// GET /api/waitlist/count - Get waitlist count (public)
router.get('/count', (_req, res) => {
  try {
    const count = db.prepare('SELECT COUNT(*) as total FROM waitlist').get();
    res.json({ count: count.total });
  } catch (err) {
    res.status(500).json({ error: 'server_error' });
  }
});

module.exports = router;
